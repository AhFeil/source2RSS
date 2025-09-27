from dataclasses import dataclass
from typing import Self

from sqlalchemy import (
    MetaData,
    asc,
    create_engine,
    desc,
    inspect,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from src.scraper import ArticleDict, SrcMetaDict

from .db_intf import DatabaseIntf
from .orm_model import ArticleBase, Base, SourceMeta4ORM


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
        source_name = source_info['table_name']
        with self.Session() as session:
            res = session.query(SourceMeta4ORM).filter_by(table_name=source_name).first()
            if res is None:
                # 元信息不存在就添加
                meta = SourceMeta4ORM(**source_info)
                session.add(meta)
                session.commit()
                self.logger.info("%s Add into source_meta", source_name)
            elif not res.equal_to(source_info):
                # 元信息不一致就更新
                res.update_from(source_info)
                session.commit()
                self.logger.info("%s Update its source_meta", source_name)
            else:
                # 元信息保持不变就跳过
                pass

    def store2database(self, table_name: str, one_article_doc: ArticleDict):
        ArticleModel = ArticleBase.get_article_model(table_name)   # 所有的也就名字不一样
        if not self._check_table_exists(table_name):
            ArticleModel.__table__.create(self.engine)
        with self.Session() as session:
            res = session.query(SourceMeta4ORM).filter_by(table_name=table_name).first()
            article = ArticleModel(website_id=res.id, **one_article_doc)
            session.add(article)
            session.commit()

    def get_source_info(self, source_name: str) -> SrcMetaDict | None:
        with self.Session() as session:
            res = session.query(SourceMeta4ORM).filter_by(table_name=source_name).first()
            return res.export_to_dict() if res else None

    def get_top_n_articles_by_key(self, source_name: str, n: int, key: str, reverse: bool=False) -> list[ArticleDict]:
        ArticleModel = ArticleBase.get_article_model(source_name)
        if not self._check_table_exists(source_name):
            ArticleModel.__table__.create(self.engine)
        column_to_sort = getattr(ArticleModel, key)
        with self.Session() as session:
            results = session.query(ArticleModel).order_by(asc(column_to_sort)).limit(n).all() if reverse else \
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
