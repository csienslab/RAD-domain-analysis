from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, BigInteger, String, Text, DateTime

Base = declarative_base()
class Crtsh(Base):
    __tablename__ = 'crtsh'
    id = Column(BigInteger, primary_key=True)
    domain = Column(String)
    result = Column(Text)
    
    def __repr__(self):
        return f'{self.id}: {self.domain} {self.result}'


class Certificate(Base):
    __tablename__ = 'certificates'
    id = Column(BigInteger, primary_key=True)
    cert = Column(Text)
    crtsh_id = Column(Text)
    #initiator = Column(Text)
    
    def __repr__(self):
        return f'{self.id}: {self.crtsh_id} {self.cert}'


class Request(Base):
    __tablename__ = 'requests'
    id = Column(BigInteger, primary_key=True)
    domain = Column(String)
    request = Column(Text)
    datetime = Column(DateTime)
    crawl_datetime = Column(DateTime)
    #initiator = Column(Text)
    
    def __repr__(self):
        return f'{self.domain}: {self.datetime} {self.request}'
