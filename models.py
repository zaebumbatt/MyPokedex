from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(30))


class Pokemon(Base):
    __tablename__ = 'pokemon'

    id = Column(String(30), primary_key=True)
    name = Column(String(255))
    hp = Column(Integer)
    image = Column(String(255))
    rarity = Column(String(255))
    supertype = Column(String(255))
    subtypes = Column(ARRAY(String(255)))
    types = Column(ARRAY(String(255)))


class Pokedex(Base):
    __tablename__ = 'pokedex'

    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    pokemon_id = Column(String(30), ForeignKey('pokemon.id'), primary_key=True)

    user = relationship('User')
    pokemon = relationship('Pokemon')
