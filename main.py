import logging
import os

from dotenv import load_dotenv
from pokemontcgsdk import Card, RestClient
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import Session
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      InputMediaPhoto, Update)
from telegram.ext import (ApplicationBuilder, CallbackContext,
                          CallbackQueryHandler, CommandHandler, MessageHandler,
                          filters)

from models import Base, MyPokedex

load_dotenv()

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
POKEMONTCG_IO_API_KEY = os.environ.get('POKEMONTCG_IO_API_KEY')
POSTGRES_USER = os.environ.get('POSTGRES_USER')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
POSTGRES_DB = os.environ.get('POSTGRES_DB')

RestClient.configure(POKEMONTCG_IO_API_KEY)

conn_url = f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db/{POSTGRES_DB}'
engine = create_engine(conn_url)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

commands = '''
/start: Start Bot
/find: Find all existing cards by the pokemon name
/show: Show the list of your cards
/delete: Delete pokemon by the pokemon id 
'''


async def start(update: Update, context: CallbackContext):
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

        cards = Card.where(q=f'name:{pokemon_name}')
        images = []
        for card in cards:
            images.append(InputMediaPhoto(media=card.images.large, caption=f'{card.id}'))

        send_message_kwargs = {
            'chat_id': update.effective_chat.id,
            'text': 'Please forward me the picture of the card that you have',
        }
        if i + 10 < len(images):
            button_list = [
                InlineKeyboardButton('Next', callback_data=f'{pokemon_name} {i + 10}'),
            ]
            send_message_kwargs['reply_markup'] = InlineKeyboardMarkup([button_list])

        await context.bot.send_media_group(
            chat_id=update.effective_chat.id,
            media=images[i:i + 10],
        )
        await context.bot.send_message(**send_message_kwargs)


async def show(update: Update, context: CallbackContext):
    message = 'Your Pokedex is empty'

    with Session(engine) as session:
        query = session.query(MyPokedex).filter(MyPokedex.user_id == update.effective_chat.id)
        pokemon_ids = []
        if query.all():
            pokemon_ids = [row.pokemon_id for row in query]

    if pokemon_ids:
        message = ''
        for i, pokemon_id in enumerate(pokemon_ids, 1):
            message += f'{i}. {Card.find(pokemon_id).name} ({pokemon_id})\n'

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message
    )


async def add_from_caption(update: Update, context: CallbackContext):
    message = 'Incorrect picture or pokemon id is missing, please try again'
    pokemon_id = update.message.caption
    if pokemon_id:
        card = Card.find(pokemon_id)

        with Session(engine) as session:
            query = session.query(MyPokedex).filter(
                and_(
                    MyPokedex.user_id == update.effective_chat.id,
                    MyPokedex.pokemon_id == pokemon_id
                )
            )
            message = f'You have {card.name} ({pokemon_id}) in your Pokedex already'
            if not query.all():
                obj = MyPokedex(
                    user_id=update.effective_user.id,
                    pokemon_id=pokemon_id
                )
                session.add(obj)
                session.commit()
                message = f'{card.name} ({pokemon_id}) has been added to your Pokedex'

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
            query = session.query(MyPokedex).filter(
                and_(
                    MyPokedex.user_id == update.effective_chat.id,
                    MyPokedex.pokemon_id == pokemon_id
                )
            )
            if query.all():
                query.delete()
                session.commit()
                card = Card.find(pokemon_id)
                message = f'{card.name} ({pokemon_id}) has been deleted from your Pokedex'

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message
    )


if __name__ == '__main__':
    Base.metadata.create_all(engine)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    start_handler = CommandHandler('start', start)
    find_handler = CommandHandler('find', find)
    show_handler = CommandHandler('show', show)
    add_from_caption = MessageHandler(filters.PHOTO, add_from_caption)
    callback_handler = CallbackQueryHandler(find)
    delete_handler = CommandHandler('delete', delete)

    application.add_handler(start_handler)
    application.add_handler(find_handler)
    application.add_handler(show_handler)
    application.add_handler(add_from_caption)
    application.add_handler(callback_handler)
    application.add_handler(delete_handler)

    application.run_polling()
