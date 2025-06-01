from typing import Generator
import imaplib
import email
import email.utils

imaplib._MAXLINE = 10000000


class Mail:
    def __init__(self, msg_id, msg):
        self._msg: str = msg
        self._parsed: bool = False

        # 这些字段是在读取邮件列表时就解析的
        self.msg_id = msg_id
        self.subject: str = self._decode_value(msg.get("subject"))
        self.date = email.utils.parsedate_to_datetime(msg.get("date"))
        from_name, self.from_addr = email.utils.parseaddr(msg.get("from"))
        self.from_name = self._decode_value(from_name)
        to_name, self.to_addr = email.utils.parseaddr(msg.get("to"))
        self.to_name = self._decode_value(to_name)

        # 这些字段是延迟到需要访问时才解析的
        self._plain: str = ""
        self._html: str = ""
        self._attachments: list = []

    def _decode_value(self, value):
        header = email.header.decode_header(value)
        raw_value, charset = header[0]
        return Mail.decode(raw_value, charset)

    @property
    def plain(self):
        # 为了延迟解析邮件内容
        if not self._parsed:
            self.parse_content()
        return self._plain

    @property
    def html(self):
        if not self._parsed:
            self.parse_content()
        return self._html

    # 解析mail的内容
    def parse_content(self):
        for part in self._msg.walk():
            if part.is_multipart():
                continue
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset()
                content = Mail.decode(part.get_payload(decode=True), charset)
                self._plain = content
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset()
                content = Mail.decode(part.get_payload(decode=True), charset)
                self._html = content
        if self._plain:
            self._html = ""
        self._parsed = True

    @staticmethod
    def decode(s, charset):
        if isinstance(s, str):
            return s
        for a_charset in (charset, "utf-8", "latin1", "gbk"):
            try:
                return s.decode(a_charset)
            except Exception:
                pass
        return "fail to decode"


class ImapMailBox:
    def __init__(self, host, port, username, password, ssl=True):
        self.host = host
        self.port = port
        self.ssl = ssl
        self.username = username
        self.password = password

    def __enter__(self):
        self.conn = imaplib.IMAP4_SSL(host=self.host, port=self.port) if self.ssl else imaplib.IMAP4(host=self.host, port=self.port)
        self.conn.login(self.username, self.password)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.logout()
        if exc_type is not None:
            print(f'an error occured while exiting ImapMailBox: {exc_value}')

    def get_mail_count(self):
        # 收件箱里的邮件数
        # Selecting the inbox
        self.conn.select('Inbox')
        state, data = self.conn.search(None, 'ALL')
        mails = data[0].split()
        return len(mails)

    def get_mails(self, flag: str="UNSEEN", reversed: bool=True) -> Generator[Mail, None, None]:
        self.conn.select('Inbox')
        state, data = self.conn.search(None, flag)
        message_ids: list = data[0].split()
        if reversed:
            message_ids.reverse()
        for msg_id in message_ids:
            state, data = self.conn.fetch(msg_id, '(RFC822)')
            raw_email = data[0][1]
            try:
                msg = email.message_from_bytes(raw_email)
                mail = Mail(msg_id, msg)
                yield mail
            except Exception as e:
                print(f"Parse raw data failed. [raw_data] '{raw_email}'\n, {e}")

    def mark_as_seen(self, mail):
        self.conn.store(mail.msg_id, '+FLAGS', '\\seen')


if __name__ == '__main__':
    mailbox = ImapMailBox(host='imap.gmail.com', port=993, username="", password="")
    print(mailbox.get_mail_count())
    # 分页获取邮件
    for mail in mailbox.get_mails("ALL"):
        # 打印 日期、发件人、标题、纯文本内容
        print(mail.date, mail.from_addr, mail.subject, mail.plain)
        break
