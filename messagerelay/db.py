from maubot import Plugin
from sqlalchemy import *
from sqlalchemy.engine.base import Engine


class MrDatabase:
    plugin: Plugin
    db: Engine

    def __init__(self, db: Engine, plugin: Plugin) -> None:
        self.plugin = plugin
        self.db = db
        meta = MetaData()
        meta.bind = db

        self.rooms = Table("rooms", meta,
                           Column("id", Integer, primary_key=True, autoincrement=True),
                           Column("room_name", String, unique=True, nullable=False),
                           Column("room_id", String(255), nullable=False)
                           )

        self.messages = Table("messages", meta,
                              Column("id", Integer, primary_key=True, autoincrement=True),
                              Column("room_name", String, nullable=False),
                              Column("room_id", String(255), nullable=False),
                              Column("message_evt_id", String(255), nullable=False),
                              Column("message_id", String(255), nullable=False),
                              Column("message_content", String, nullable=False),
                              Column("deleted", Boolean, nullable=False)
                              )

        meta.create_all()

    def update_room(self, room_name: str, room_id: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO rooms(room_name, room_id) VALUES(?,?)", (room_name, room_id))

    def update_room_id(self, room_id_old: str, room_id_new) -> None:
        self.db.execute("UPDATE rooms SET room_id=? WHERE room_id=?", (room_id_new, room_id_old))

    def save_message(self, room_name: str, room_id: str, message_evt_id: str, message_id: str, message_content: str):
        self.db.execute("INSERT INTO messages(room_name, room_id, message_evt_id, message_id, message_content, deleted)"
                        " VALUES(?,?,?,?,?,?)",
                        (room_name, room_id, message_evt_id, message_id, message_content, False))

    def get_room_id(self, room_name: str):
        result = self.db.execute(self.rooms.select().where(self.rooms.c.room_name == room_name)).fetchone()
        return result

    def get_evt_by_message_id(self, message_id):
        result = self.db.execute("SELECT room_id, message_evt_id FROM messages WHERE message_id=?",
                                 (message_id,)).fetchone()
        return result

    def message_set_deleted(self, message_id):
        self.db.execute(self.messages.update().where(self.messages.c.message_id == message_id)
                        .values(deleted=True))
