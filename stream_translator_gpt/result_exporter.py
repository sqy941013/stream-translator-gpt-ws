import os
import queue
import requests
import json
from websockets.server import serve
import asyncio
import threading

from .common import TranslationTask, LoopWorkerBase, sec2str


def _send_to_cqhttp(url: str, token: str, proxies: dict, text: str):
    headers = {'Authorization': 'Bearer {}'.format(token)} if token else None
    data = {'message': text}
    try:
        requests.post(url, headers=headers, data=data, timeout=10, proxies=proxies)
    except Exception as e:
        print(e)


def _send_to_discord(webhook_url: str, proxies: dict, text: str):
    for sub_text in text.split('\n'):
        data = {'content': sub_text}
        try:
            requests.post(webhook_url, json=data, timeout=10, proxies=proxies)
        except Exception as e:
            print(e)


def _send_to_telegram(token: str, chat_id: int, proxies: dict, text: str):
    url = 'https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}'.format(token, chat_id, text)
    try:
        requests.post(url, timeout=10, proxies=proxies)
    except Exception as e:
        print(e)


def _output_to_file(file_path: str, text: str):
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(text + '\n\n')


class WebSocketServer:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.connected_clients = set()
        self._server = None
        self._server_task = None

    async def handler(self, websocket):
        self.connected_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.connected_clients.remove(websocket)

    async def broadcast(self, message):
        if not self.connected_clients:
            return
        await asyncio.gather(
            *[client.send(message) for client in self.connected_clients]
        )

    async def start_server(self):
        self._server = await serve(self.handler, self.host, self.port)
        print(f'WebSocket server started at ws://{self.host}:{self.port}')
        await self._server.wait_closed()

    def run_in_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.start_server())

    def start(self):
        thread = threading.Thread(target=self.run_in_thread, daemon=True)
        thread.start()
        return thread


class ResultExporter(LoopWorkerBase):
    def __init__(self, output_file_path: str, ws_host: str = 'localhost', ws_port: int = 8765) -> None:
        if output_file_path:
            if os.path.exists(output_file_path):
                os.remove(output_file_path)
        
        # Initialize WebSocket server
        self.ws_server = WebSocketServer(ws_host, ws_port)
        self.ws_server.start()

    @classmethod
    def work(cls, input_queue: queue.SimpleQueue[TranslationTask], output_whisper_result: bool,
            output_timestamps: bool, proxy: str, output_file_path: str, cqhttp_url: str, cqhttp_token: str,
            discord_webhook_url: str, telegram_token: str, telegram_chat_id: int, ws_host: str = 'localhost',
            ws_port: int = 8765):
        instance = cls(output_file_path=output_file_path, ws_host=ws_host, ws_port=ws_port)
        instance.loop(
            input_queue=input_queue,
            output_whisper_result=output_whisper_result,
            output_timestamps=output_timestamps,
            proxy=proxy,
            output_file_path=output_file_path,
            cqhttp_url=cqhttp_url,
            cqhttp_token=cqhttp_token,
            discord_webhook_url=discord_webhook_url,
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id
        )

    def loop(self, input_queue: queue.SimpleQueue[TranslationTask], output_whisper_result: bool,
             output_timestamps: bool, proxy: str, output_file_path: str, cqhttp_url: str, cqhttp_token: str,
             discord_webhook_url: str, telegram_token: str, telegram_chat_id: int):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        while True:
            task = input_queue.get()
            timestamp_text = '{} --> {}'.format(sec2str(task.time_range[0]), sec2str(task.time_range[1]))
            text_to_send = (task.transcribed_text + '\n') if output_whisper_result else ''
            if output_timestamps:
                text_to_send = timestamp_text + '\n' + text_to_send
            if task.translated_text:
                text_to_print = task.translated_text
                if output_timestamps:
                    text_to_print = timestamp_text + ' ' + text_to_print
                text_to_print = text_to_print.strip()
                print('\033[1m{}\033[0m'.format(text_to_print))
                text_to_send += task.translated_text
            text_to_send = text_to_send.strip()
            if output_file_path:
                _output_to_file(output_file_path, text_to_send)
            if cqhttp_url:
                _send_to_cqhttp(cqhttp_url, cqhttp_token, proxies, text_to_send)
            if discord_webhook_url:
                _send_to_discord(discord_webhook_url, proxies, text_to_send)
            if telegram_token and telegram_chat_id:
                _send_to_telegram(telegram_token, telegram_chat_id, proxies, text_to_send)
            
            # Send to WebSocket clients
            ws_data = {
                'timestamp': timestamp_text if output_timestamps else None,
                'transcribed_text': task.transcribed_text if output_whisper_result else None,
                'translated_text': task.translated_text,
                'time_range': [task.time_range[0], task.time_range[1]]
            }
            asyncio.get_event_loop().run_until_complete(
                self.ws_server.broadcast(json.dumps(ws_data))
            )
