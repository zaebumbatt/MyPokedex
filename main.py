import logging
import os

from dotenv import load_dotenv
from pokemontcgsdk import Card, RestClient
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import Session
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      InputMediaPhoto, Update)
from telegram.error import BadRequest
from telegram.ext import (ApplicationBuilder, CallbackContext,
                          CallbackQueryHandler, CommandHandler, MessageHandler,
                          filters)

from models import Base, Pokedex, Pokemon, User

load_dotenv()

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
POKEMONTCG_IO_API_KEY = os.environ.get('POKEMONTCG_IO_API_KEY')
POSTGRES_USER = os.environ.get('POSTGRES_USER')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
POSTGRES_DB = os.environ.get('POSTGRES_DB')
POSTGRES_HOST_PORT = os.environ.get('POSTGRES_HOST_PORT')

RestClient.configure(POKEMONTCG_IO_API_KEY)

conn_url = f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST_PORT}/{POSTGRES_DB}'
engine = create_engine(conn_url)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

commands = '''
/start: Start Bot
/find: Find all existing cards by the pokemon name
/list: Show the list of your cards
/delete: Delete pokemon by the pokemon id 
'''


async def start(update: Update, context: CallbackContext):
    with Session(engine) as session:
        existing_user = session.query(User).filter(User.id == update.effective_user.id).first()
        if not existing_user:
            user = User(
                id=update.effective_user.id,
                username=update.effective_user.username,
            )
            session.add(user)
            session.commit()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Hello. Check the list of the commands:\n {commands}'
    )


async def find(update: Update, context: CallbackContext):
    if not update.callback_query and not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Please specify the pokemon name after the command'
        )
    else:
        if context.args:
            pokemon_name = context.args[0]
            i = 0
        if update.callback_query:
            pokemon_name, i = update.callback_query.data.split()
            i = int(i)
            await update.callback_query.answer()

        cards = Card.where(q=f'name:{pokemon_name}')
        send_message_kwargs = {
            'chat_id': update.effective_chat.id,
            'text': 'Sorry, no pokemons found with this name',
        }
        if cards:
            images = []
            for card in cards:
                images.append(InputMediaPhoto(media=card.images.large, caption=f'{card.id}'))

            if i + 10 < len(images):
                button_list = [
                    InlineKeyboardButton('Next', callback_data=f'{pokemon_name} {i + 10}'),
                ]
                send_message_kwargs['reply_markup'] = InlineKeyboardMarkup([button_list])

            send_message_kwargs['text'] = 'Please forward me the picture of the card that you have'
            for j in range(-1, len(images[i:i + 10])):
                media = images[i:i + 10] if j == -1 else images[i:i + j] + images[i + j + 1:i + 10]
                try:
                    await context.bot.send_media_group(
                        chat_id=update.effective_chat.id,
                        media=media,
                    )
                    break
                except BadRequest:
                    continue
        await context.bot.send_message(**send_message_kwargs)


async def list(update: Update, context: CallbackContext):
    message = 'Your Pokedex is empty'

    with Session(engine) as session:
        query = session.query(Pokedex).filter(Pokedex.user_id == update.effective_user.id)
        pokemons = [(row.pokemon.id, row.pokemon.name) for row in query] if query.all() else []

    if pokemons:
        pokemons.sort(key=lambda x: (x[1], x[0]))
        message = ''
        for i, (pokemon_id, pokemon_name) in enumerate(pokemons, 1):
            message += f'{i}. {pokemon_name} ({pokemon_id})\n'

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message
    )


async def add_from_caption(update: Update, context: CallbackContext):
    message = 'Incorrect picture or pokemon id is missing, please try again'
    pokemon_id = update.message.caption
    if pokemon_id:
        with Session(engine) as session:
            existing_pokemon = session.query(Pokemon).filter(Pokemon.id == pokemon_id).first()
            if not existing_pokemon:
                card = Card.find(pokemon_id)
                pokemon = Pokemon(
                    id=card.id,
                    name=card.name,
                    hp=card.hp,
                    image=card.images.large,
                    rarity=card.rarity,
                    supertype=card.supertype,
                    subtypes=card.subtypes,
                    types=card.types,
                )
                session.add(pokemon)
                session.commit()

        with Session(engine) as session:
            query = session.query(Pokedex).filter(
                and_(
                    Pokedex.user_id == update.effective_user.id,
                    Pokedex.pokemon_id == pokemon_id
                )
            )
            pokemon = session.query(Pokemon).filter(Pokemon.id == pokemon_id).first()
            message = f'You have {pokemon.name} ({pokemon.id}) in your Pokedex already'
            if not query.all():
                obj = Pokedex(
                    user_id=update.effective_user.id,
                    pokemon_id=pokemon.id
                )
                session.add(obj)
                session.commit()
                message = f'{pokemon.name} ({pokemon.id}) has been added to your Pokedex'

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message
    )


async def delete(update: Update, context: CallbackContext):
    message = 'Please specify the pokemon id after the command'
    if context.args:
        pokemon_id = context.args[0]
        with Session(engine) as session:
            message = "You don't have a pokemon with this id"
            query = session.query(Pokedex).filter(
                and_(
                    Pokedex.user_id == update.effective_user.id,
                    Pokedex.pokemon_id == pokemon_id
                )
            )
            if query.all():
                pokemon = session.query(Pokemon).filter(Pokemon.id == pokemon_id).first()
                query.delete()
                session.commit()
                message = f'{pokemon.name} ({pokemon.id}) has been deleted from your Pokedex'

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message
    )


if __name__ == '__main__':
    Base.metadata.create_all(engine)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    start_handler = CommandHandler('start', start)
    find_handler = CommandHandler('find', find)
    list_handler = CommandHandler('list', list)
    add_from_caption = MessageHandler(filters.PHOTO, add_from_caption)
    callback_handler = CallbackQueryHandler(find)
    delete_handler = CommandHandler('delete', delete)

    application.add_handler(start_handler)
    application.add_handler(find_handler)
    application.add_handler(list_handler)
    application.add_handler(add_from_caption)
    application.add_handler(callback_handler)
    application.add_handler(delete_handler)

    application.run_polling()
