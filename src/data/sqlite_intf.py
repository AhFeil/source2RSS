from dataclasses import dataclass
from typing import Self

from sqlalchemy import create_engine, inspect, MetaData, Column, Integer, String, DateTime, ForeignKey, asc, desc
from sqlalchemy.orm import declarative_base, sessionmaker, declared_attr
from sqlalchemy.sql import text

from .db_intf import DatabaseIntf
from src.website_scraper.scraper import SrcMetaDict, ArticleDict


Base = declarative_base()

class SourceMeta4ORM(Base):
    __tablename__ = "source_meta"  # config.source_meta

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)   # 同样作为文章表的名称
    link = Column(String)
    desc = Column(String)
    lang = Column(String)
    key4sort = Column(String(30), nullable=False)
    access = Column(Integer)

    def __repr__(self):
        return f"<SourceMeta(id={self.id}, name='{self.name}', link='{self.link}', desc='{self.desc}', lang='{self.lang}', key4sort={self.key4sort})>"

    def equal_to(self, source_info: SrcMetaDict) -> bool:
        # 如果缺少键，运行时不会报错 KeyError ，而是会卡死
        return all(getattr(self, column.name) == source_info[column.name] for column in self.__table__.columns if not column.primary_key)

    def update_from(self, source_info: SrcMetaDict):
        for column in self.__table__.columns:
            if column.primary_key:
                continue
            setattr(self, column.name, source_info[column.name])

    def export_to_dict(self) -> SrcMetaDict:
        source_info = {}
        for column in self.__table__.columns:
            if column.primary_key:
                continue
            source_info[column.name] = getattr(self, column.name)
        return source_info # type: ignore


article_models: dict[str, type] = {}

class ArticleBase:
    """动态文章表的基类"""
    t_id = Column(Integer, primary_key=True)
    id = Column(Integer)
    title = Column(String)
    summary = Column(String)
    link = Column(String)
    image_link = Column(String)
    content = Column(String)
    pub_time = Column(DateTime, index=True)
    chapter_number = Column(Integer, index=True)
    time4sort = Column(DateTime, index=True)
    num4sort = Column(Integer, index=True)
    # 动态外键关联（需要创建时赋值）
    @declared_attr
    def website_id(cls):
        return Column(Integer, ForeignKey('source_meta.id'))  # config.source_meta

    def export_to_dict(self) -> ArticleDict:
        article = {}
        for column in self.__table__.columns: # type: ignore
            if column.primary_key or column.name == "website_id":
                continue
            article[column.name] = getattr(self, column.name)
        return article # type: ignore

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, title='{self.title}', pub_time={self.pub_time})>"

    @staticmethod
    def create_article_model(source_name) -> type:
        """动态创建文章表的工厂函数"""
        class_name = f"ArticleOf{source_name}"
        # 使用type动态创建类
        return type(
            class_name,
            (ArticleBase, Base),
            {
                '__tablename__': source_name,
                '__mapper_args__': {
                    'polymorphic_identity': source_name
                }
            }
        )
    # 运行时，如果创建两次就会出错，因此需要缓存结果，非线程安全
    @staticmethod
    def get_article_model(source_name) -> type:
        """获取动态创建的文章表模型"""
        if article_models.get(source_name):
            return article_models[source_name]
        ArticleModel = ArticleBase.create_article_model(source_name)
        article_models[source_name] = ArticleModel
        return ArticleModel


@dataclass
class SQliteConnInfo:
    sqlite_uri: str


class SQliteIntf(DatabaseIntf):
    @classmethod
    def connect(cls, info: SQliteConnInfo) -> Self:
        engine = create_engine(info.sqlite_uri)
        # 创建表（如果不存在）
        Base.metadata.create_all(engine)
        # 创建会话工厂
        Session = sessionmaker(bind=engine)
        return cls(engine, Session)

    def exist_source_meta(self, source_info: SrcMetaDict):
        source_name = source_info['name']
        with self.Session() as session:
            res = session.query(SourceMeta4ORM).filter_by(name=source_name).first()
            if res is None:
                # 元信息不存在就添加
                meta = SourceMeta4ORM(**source_info)
                session.add(meta)
                session.commit()
                self.logger.info(f"{source_name} Add into source_meta")
            elif not res.equal_to(source_info):
                # 元信息不一致就更新
                res.update_from(source_info)
                session.commit()
                self.logger.info(f"{source_name} Update its source_meta")
            else:
                # 元信息保持不变就跳过
                pass

    def store2database(self, source_name: str, one_article_doc: ArticleDict):
        ArticleModel = ArticleBase.get_article_model(source_name)   # 也就名字不一样
        if not self._check_table_exists(source_name):
            ArticleModel.__table__.create(self.engine)
        with self.Session() as session:
            res = session.query(SourceMeta4ORM).filter_by(name=source_name).first()
            article = ArticleModel(website_id=res.id, **one_article_doc)
            session.add(article)
            session.commit()

    def get_source_info(self, source_name: str) -> SrcMetaDict | None:
        with self.Session() as session:
            res = session.query(SourceMeta4ORM).filter_by(name=source_name).first()
            return res.export_to_dict() if res else None

    def get_top_n_articles_by_key(self, source_name: str, n: int, key: str, reversed: bool=False) -> list[ArticleDict]:
        ArticleModel = ArticleBase.get_article_model(source_name)
        if not self._check_table_exists(source_name):
            ArticleModel.__table__.create(self.engine)
        column_to_sort = getattr(ArticleModel, key)
        with self.Session() as session:
            results = session.query(ArticleModel).order_by(asc(column_to_sort)).limit(n).all() if reversed else \
                      session.query(ArticleModel).order_by(desc(column_to_sort)).limit(n).all()
            if results is None:
                return []
            return [res.export_to_dict() for res in results]

    def _clear_db(self):
        metadata = MetaData()
        # 反射数据库结构
        metadata.reflect(bind=self.engine)
        # 开始事务
        with self.engine.begin() as connection:
            # 禁用外键约束
            connection.execute(text("PRAGMA foreign_keys = OFF"))
            for table in metadata.tables.values():
                connection.execute(table.delete())
            # 重新启用外键约束
            connection.execute(text("PRAGMA foreign_keys = ON"))

    def __init__(self, engine, Session):
        super().__init__()
        self.engine = engine
        self.Session = Session

    def _check_table_exists(self, table_name: str) -> bool:
        """检查 SQLite 数据库中是否存在指定名称的表"""
        inspector = inspect(self.engine)
        return inspector.has_table(table_name)


if __name__ == "__main__":
    from datetime import datetime

    info = SQliteConnInfo("sqlite:///config_and_data_files/test.db")
    db_intf: DatabaseIntf = SQliteIntf.connect(info)

    db_intf._clear_db()
    source_info: SrcMetaDict = {
        'name': 'BentoML Blog',
        'link': 'https://www.bentoml.com/blog',
        'desc': "description---------",
        'lang': "En",
        'key4sort': 'pub_time'
    }
    db_intf.exist_source_meta(source_info)
    assert db_intf.get_source_info(source_info["name"]) == source_info
    source_info["desc"] = "szdbdxgnxmhxfm"
    db_intf.exist_source_meta(source_info)
    assert db_intf.get_source_info(source_info["name"]) == source_info

    article: ArticleDict = {
        "id": 33,
        "title": "res.title",
        "summary": "res.summary",
        "link": "res.article_url",
        "image_link": "res.image_link",
        "pub_time": datetime.now(),
        "content": "res.content",
        "chapter_number": 0
    }
    db_intf.store2database(source_info["name"], article)
    a = db_intf.get_top_n_articles_by_key(source_info["name"], 1, source_info["key4sort"])
    assert a[0] == article

    # .env/bin/python -m src.data.sqlite_intf
