from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, BigInteger, String, Text, DateTime

# Thread-local Sessions object
class Session():
    def __init__(self):
        self.engine = create_engine('mysql+pymysql://<redacted>/wayback_machine_crawl')
        self._Session = scoped_session(sessionmaker(bind=self.engine))
        self.session = self._Session()
    def __enter__(self):
        return self.session
    def __exit__(self, type, value, traceback):
        self.session.close()
        self._Session.remove()
        self._Session.close()
        self.engine.dispose()
