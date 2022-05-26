from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MyPokedex(Base):
    __tablename__ = 'my_pokedex'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    pokemon_id = Column(String(30))

    def __repr__(self):
        return f'User {self.user_id} owns pokemon {self.pokemon_id}'
