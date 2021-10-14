from maubot import Plugin
from maubot.handlers import command, event
from mautrix.types import MessageEvent, RoomID, MessageType, EventType, StateEvent
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from typing import Type
from websockets import connect
import asyncio
import json

from .db import MrDatabase


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("admin")
        helper.copy("api_key")
        helper.copy("api_uri")


class Messagerelay(Plugin):
    db: MrDatabase

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def start(self) -> None:
        self.log.debug('startup')
        await super().start()
        self.config.load_and_update()
        self.db = MrDatabase(self.database, self)
        asyncio.ensure_future(self.websocket())

    async def websocket(self) -> None:

        api_key = self.config["api_key"]
        api_uri = self.config["api_uri"]

        if api_key == "" or api_uri == "":
            self.log.error("API key or uri is not set!")
        else:
            async with connect(api_uri) as websocket:
                data = {'type': 'code', 'code': api_key}
                await websocket.send(json.dumps(data))

                while True:
                    r: json = json.loads(await websocket.recv())

                    if r.get('type') == 'verified':
                        self.log.debug(f'connected to websocket at {api_uri}')
                    elif r.get('type') == 'error':
                        self.log.error(f'[ERROR]: {r.get("msg")}')
                    elif r.get('type') == 'create':
                        self.log.info(f'new message ({r.get("id")}) to {r.get("target")}: {r.get("content")}')

                        room_name = r.get("target")
                        room_id: RoomID = RoomID(self.db.get_room_id(room_name)[2])

                        if room_id is None:
                            self.log.debug(f"Target '{room_name}' is not mapped to room.")
                        else:
                            content = r.get("content")
                            self.log.info(f"Sending message to {room_id}")
                            msg_event_id = await self.client.send_markdown(room_id=room_id,
                                                                           markdown=content,
                                                                           allow_html=True,
                                                                           msgtype=MessageType.TEXT
                                                                           )
                            self.db.save_message(room_name, room_id, msg_event_id, r.get("id"), content)

                    elif r.get('type') == 'delete':
                        msg_id = r.get("id")
                        self.log.info(f'delete message: {msg_id} from room {room_id} / evt: {evt_id}')

                        result = self.db.get_evt_by_message_id(msg_id)
                        room_id = result[0]
                        evt_id = result[1]

                        await self.client.redact(
                            room_id=room_id,
                            reason="deleted with MessageRelayLite",
                            event_id=evt_id
                        )

                        self.db.message_set_deleted(msg_id)

    @command.new("mrroom", aliases=["messagerelay", "mr-room"],
                 help="Admincommand to set rooms for the messagerelay(light) !mrroom <room_name>.")
    @command.argument("room_name", pass_raw=True, required=True)
    async def messagerelay(self, evt: MessageEvent, room_name: str):
        room_id = evt.room_id
        if evt.sender == self.config["admin"]:
            self.db.update_room(room_name, room_id)
            await evt.respond(f"Binding {room_name} to this room")
        else:
            await evt.respond("You do not have the permission to bind a room.")

    @event.on(EventType.ROOM_TOMBSTONE)
    async def handle_tombstone(self, evt: StateEvent):

        old_room = evt.room_id
        new_room = evt.content.replacement_room

        self.log.info(f"{old_room} was upgraded to {new_room}")
        self.db.update_room_id(old_room, new_room)
