import asyncio
import traceback
import base64
import json
import shutil
import os
import random
import re
import datetime
import brotli
import functools
import string

from typing import Callable
from multiprocessing.util import debug
from time import time
from urllib.parse import unquote, quote

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import (
    Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan,
    AuthKeyDuplicated, SessionExpired, SessionRevoked, FloodWait
)
from pyrogram.raw import types
from pyrogram.raw import functions

from bot.config import settings

from bot.utils import logger
from bot.exceptions import TelegramInvalidSessionException, TelegramProxyError
from .headers import headers

from random import randint, choices

from bot.utils.functions import card_details, tapHash, generate_taps, task_answer, combo_answer, count_spin

from ..utils.firstrun import append_line_to_file

def error_handler(func: Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            await asyncio.sleep(1)
    return wrapper


class Tapper:
    def __init__(self, tg_client: Client, first_run: bool):
        self.tg_client = tg_client
        self.first_run = first_run
        self.session_name = tg_client.name
        self.start_param = ''
        self.main_bot_peer = 'bums'
        self.joined = None
        self.balance = 0
        self.template_to_join = 0
        self.user_id = 0

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                await self.tg_client.connect()
            
            while True:
                try:
                    peer = await self.tg_client.resolve_peer('bums')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"{self.session_name} | FloodWait {fl}")
                    logger.info(f"{self.session_name} | Sleep {fls}s")
                    await asyncio.sleep(fls + 3)

            ref_key = random.choice([settings.REF_KEY, "ref_3CcrQyaN"]) if settings.SUPPORT_AUTHOR else settings.REF_KEY
            ref_id = ref_key.removeprefix("ref_")
            
            web_view = await self.tg_client.invoke(functions.messages.RequestAppWebView(
                peer=peer,
                app=types.InputBotAppShortName(bot_id=peer, short_name="app"),
                platform='android',
                write_allowed=True,
                start_param=ref_key
            ))

            auth_url = web_view.url
            tg_web_data = unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            me = await self.tg_client.get_me()
            self.tg_client_id = me.id
            
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return ref_id, tg_web_data

        except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
                SessionExpired, SessionRevoked):
            raise TelegramInvalidSessionException(f"Telegram session is invalid. Client: {self.tg_client.name}")
        except AttributeError as e:
            raise TelegramProxyError(e)
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)
            
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

    @error_handler  
    async def join_and_mute_tg_channel(self, link: str):
        await asyncio.sleep(delay=random.randint(15, 30))
        
        if not self.tg_client.is_connected:
            await self.tg_client.connect()
    
        try:
            # Parse the link
            parsed_link = link if 'https://t.me/+' in link else link[13:]
            
            # Retrieve chat details
            chat = await self.tg_client.get_chat(parsed_link)
            
            # Determine username or ID
            if chat.username:
                chat_username = chat.username
            elif chat.id:
                chat_username = chat.id
            else:
                logger.error("Unable to get channel username or id")
                return
            
            logger.info(f"{self.session_name} | Retrieved channel: <y>{chat_username}</y>")
    
            # Check if already a member
            try:
                await self.tg_client.get_chat_member(chat_username, "me")
            except Exception as error:
                if getattr(error, "ID", None) == 'USER_NOT_PARTICIPANT':
                    # Join the channel if not a member
                    await asyncio.sleep(delay=3)
                    chat = await self.tg_client.join_chat(parsed_link)
                    chat_id = chat.id
                    logger.info(f"{self.session_name} | Successfully joined chat <y>{chat_username}</y>")
                    
                    # Wait before muting
                    await asyncio.sleep(random.randint(5, 10))
                    
                    # Resolve the peer
                    if chat.is_channel or chat.is_group:
                        peer = types.InputPeerChannel(channel_id=chat.id, access_hash=chat.access_hash)
                    else:
                        logger.error(f"{self.session_name} | Unsupported chat type for {chat_username or chat_id}")
                        return
                    
                    # Mute the chat
                    await self.tg_client.invoke(functions.account.UpdateNotifySettings(
                        peer=peer,
                        settings=types.InputPeerNotifySettings(mute_until=2147483647)
                    ))
                    logger.info(f"{self.session_name} | Successfully muted chat <y>{chat_username}</y>")
                else:
                    logger.error(f"{self.session_name} | Error while checking channel: <y>{chat_username}</y>: {str(error)}")
        except Exception as e:
            logger.error(f"{self.session_name} | Error joining/muting channel {link}: {str(e)}")
            await asyncio.sleep(delay=3)    
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            await asyncio.sleep(random.randint(10, 20))
        
    @error_handler
    async def change_tg_name(self, name: str):
        await asyncio.sleep(delay=random.randint(15, 30))
        
        if not self.tg_client.is_connected:
            await self.tg_client.connect()
    
        try:
            me = await self.tg_client.get_me()
            current_first_name = me.first_name
            current_last_name = me.last_name or ""
            if name in current_last_name:
                return
            
            updated_last_name = f"{current_last_name} {name}".strip()
            await self.tg_client.update_profile(last_name=updated_last_name)
            logger.info(f"{self.session_name} | Successfully updated last name to: <y>{current_first_name} {updated_last_name}</y>")
        except Exception as e:
            logger.error(f"{self.session_name} | Error updating last name: {str(e)}")
        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            await asyncio.sleep(random.randint(10, 20))
            
    @error_handler
    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='http://ip-api.com/json', timeout=aiohttp.ClientTimeout(20))
            response.raise_for_status()

            response_json = await response.json()
            ip = response_json.get('query', 'N/A')
            country = response_json.get('country', 'N/A')

            logger.info(f"{self.session_name} | Proxy IP : {ip} | Proxy Country : {country}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")
                   
    @error_handler
    async def make_request(
        self,
        http_client: aiohttp.ClientSession,
        method,
        endpoint=None,
        url=None,
        extra_headers=None,
        web_boundary=None,
        json_data=None,
        urlencoded_data=None,
        **kwargs
        ):
        
        full_url = url or f"https://api.bums.bot{endpoint or ''}"
        
        request_headers = http_client._default_headers.copy()
        if extra_headers:
            request_headers.update(extra_headers)
            
        if web_boundary:
            boundary = "------WebKitFormBoundary" + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            body = "\r\n".join(
                f"{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}"
                for key, value in web_boundary.items()
            ) + f"\r\n{boundary}--\r\n"

            request_headers["Content-Type"] = f"multipart/form-data; boundary=----{boundary.strip('--')}"
            kwargs["data"] = body
            
        elif json_data is not None:
            request_headers["Content-Type"] = "application/json"
            kwargs["json"] = json_data

        elif urlencoded_data is not None:
            request_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            kwargs["data"] = aiohttp.FormData(urlencoded_data)

        try:
            response = await http_client.request(method, full_url, headers=request_headers, **kwargs)
            response.raise_for_status()
            
            response_text = await response.text()
            
            # with open("log.txt", "a") as log_file:
            #     log_file.write(f"- URL : {full_url}\n")
            #     if method =='POST':
            #         log_file.write(f"- Post Data : {kwargs.get('data', None)}\n\n")
            #     log_file.write(f"- Response {response.status} : {response_text}\n")
            #     log_file.write(f"\n=======================================================\n")
                
            return await response.json()
        except (aiohttp.ClientResponseError, aiohttp.ClientError, Exception) as error:
            logger.error(f"{self.session_name} | Unknown error when processing request: {error}")
            raise
        
    @error_handler
    async def login(self, http_client: aiohttp.ClientSession, ref_id, init_data):
        additional_headers = {'Authorization': 'Bearer false'}
        web_boundary = {
            "invitationCode": ref_id,
            "initData": init_data
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/user/telegram_auth", extra_headers=additional_headers, web_boundary=web_boundary)
        if response and response.get("data", {}).get("token"):
            return response
        return None

    @error_handler
    async def user_data(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}

        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/user_game_level/getGameInfo", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def upgrade_tap(self, http_client: aiohttp.ClientSession, auth_token, card_type):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "type": card_type
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/user_game_level/upgradeLeve", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def get_tap_cards(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        
        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/mine/getMineLists", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def upgrade_mine(self, http_client: aiohttp.ClientSession, auth_token, mineId):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "mineId": mineId
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/mine/upgrade", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def sign_in_data(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}

        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/sign/getSignLists", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def sign_in(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "": "undefined"
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/sign/sign", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def get_tap_info(self, http_client: aiohttp.ClientSession, auth_token):
        user_data = await self.user_data(http_client, auth_token=auth_token)
    
        if not user_data or user_data.get('code') != 0:
            logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
            return None
    
        try:
            prop_info = user_data['data'].get('propInfo')
            auto_click = False
            if prop_info:
                auto_click = any(prop.get('source') == 'autoClick' for prop in prop_info)
            tap_data = {
                "balance": int(user_data['data']['gameInfo'].get('coin', 0)),
                "todayCoin": int(user_data['data']['gameInfo'].get('todayCollegeCoin', 0)),
                "todayCoinLimit": int(user_data['data']['gameInfo'].get('todayMaxCollegeCoin', 0)),
                "leftEnergy": int(user_data['data']['gameInfo'].get('energySurplus', 0)),
                "totalEnergy": int(user_data['data']['tapInfo']['energy'].get('value', 0)),
                "recovery": int(user_data['data']['tapInfo']['recovery'].get('value', 0)),
                "tap": int(user_data['data']['tapInfo']['tap'].get('value', 0)),
                "bonusChance": int(user_data['data']['tapInfo']['bonusChance'].get('value', 0)),
                "bonusRatio": int(user_data['data']['tapInfo']['bonusRatio'].get('value', 0)),
                "collectSeqNo": int(user_data['data']['tapInfo']['collectInfo'].get('collectSeqNo', 0)),
                "autoClick": auto_click
            }
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"{self.session_name} | Error parsing tap data: {e}")
            return None
    
        return tap_data
    
    @error_handler
    async def submit_taps(self, http_client: aiohttp.ClientSession, auth_token, collect_seq, taps_amount, hashCode):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "hashCode": hashCode,
            "collectSeqNo": collect_seq,
            "collectAmount": taps_amount
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/user_game/collectCoin", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def get_tasklist(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}

        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/task/lists", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def done_task(self, http_client: aiohttp.ClientSession, auth_token, task_id, pwd=None):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        urlencoded_data = {
            "id": task_id
        }
        if pwd:
            urlencoded_data["pwd"] = pwd

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/task/finish_task", extra_headers=additional_headers, urlencoded_data=urlencoded_data)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def get_refer_wallet(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}

        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/wallet/balance", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def collect_refer_wallet(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "": "undefined"
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/wallet/W70001To80001", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def get_gang_list(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "boostNum": 100,
            "powerNum": 0
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/gang/gang_lists", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def join_gang(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "name": settings.GANG_USERNAME
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/gang/gang_join", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def combo_details(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        
        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/mine_active/getMineAcctiveInfo", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK' and int(response['data'].get('resultNum')) > 0:
            return response
        return None
    
    @error_handler
    async def submit_combo(self, http_client: aiohttp.ClientSession, auth_token, one, two, three):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "cardIdStr": f"{one},{two},{three}"
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/mine_active/JoinMineAcctive", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def box_info(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        
        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/prop_shop/Lists?showPages=spin&page=1&pageSize=10", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def open_box(self, http_client: aiohttp.ClientSession, auth_token, count, prop_id):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "count": count,
            "propId": prop_id
        }

        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/game_spin/Start", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('rewardLists'):
            return response
        return None
    
    @error_handler
    async def spin_info(self, http_client: aiohttp.ClientSession, auth_token):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        
        response = await self.make_request(http_client, 'GET', endpoint="/miniapps/api/game_slot/stamina", extra_headers=additional_headers)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None
    
    @error_handler
    async def start_spin(self, http_client: aiohttp.ClientSession, auth_token, count):
        additional_headers = {'Authorization': 'Bearer ' + auth_token}
        web_boundary = {
            "count": count
        }
        response = await self.make_request(http_client, 'POST', endpoint="/miniapps/api/game_slot/start", extra_headers=additional_headers, web_boundary=web_boundary)
        if response.get('code') == 0 and response.get('msg') == 'OK':
            return response
        return None

    async def run(self, user_agent: str, proxy: str | None) -> None:
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        headers["User-Agent"] = user_agent

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn, trust_env=True) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            delay = randint(settings.START_DELAY[0], settings.START_DELAY[1])
            logger.info(f"{self.session_name} | Starting in {delay} seconds")
            await asyncio.sleep(delay=delay)
            
            while True:
                try:
                    if settings.NIGHT_MODE:
                        current_utc_time = datetime.datetime.utcnow().time()

                        start_time = datetime.time(settings.NIGHT_TIME[0], 0)
                        end_time = datetime.time(settings.NIGHT_TIME[1], 0)

                        next_checking_time = randint(settings.NIGHT_CHECKING[0], settings.NIGHT_CHECKING[1])

                        if start_time <= current_utc_time <= end_time:
                            logger.info(f"{self.session_name} | Night-Mode is on, The current UTC time is {current_utc_time.replace(microsecond=0)}, next check-in on {round(next_checking_time / 3600, 1)} hours.")
                            await asyncio.sleep(next_checking_time)
                            continue

                    sleep_time = randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
                    
                    try:
                        ref_id, init_data = await self.get_tg_web_data(proxy=proxy)
                    except TelegramProxyError:
                        return logger.error(f"<r>The selected proxy cannot be applied to the Telegram client.</r>")
                    except Exception as e:
                        return logger.error(f"Stop Tapper. Reason: {e}")
            
                    logger.info(f"{self.session_name} | Trying to login")
                    
                    # Login
                    login_data = await self.login(http_client, ref_id=ref_id, init_data=init_data)
                    if not login_data:
                        logger.error(f"{self.session_name} | Login Failed")
                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                        await asyncio.sleep(delay=sleep_time)
                        continue
                    
                    auth_token = login_data.get("data", {}).get("token")
                    
                    logger.success(f"{self.session_name} | <g>📦 Login Successful</g>")
                    
                    # User-Data
                    user_data = await self.user_data(http_client, auth_token=auth_token)
                    if not user_data:
                        logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                        await asyncio.sleep(delay=sleep_time)
                        break
                    
                    balance_coin = user_data['data']['gameInfo'].get('coin') or 0
                    current_level = user_data['data']['gameInfo'].get('level') or 0
                    profit_hour = user_data['data']['mineInfo'].get('minePower') or 0
                    offline_bonus = int(user_data['data']['mineInfo'].get('mineOfflineCoin'))
                    
                    logger.info(f"{self.session_name} | Balance : <y>{balance_coin}</y> | Level : <y>{current_level}</y> | Profit Per Hour : <y>{profit_hour}</y>")
                    
                    if offline_bonus > 0:
                        logger.success(f"{self.session_name} | Collected Offline Bonus: <g>+{offline_bonus}</g>")
                        
                    await asyncio.sleep(random.randint(1, 3))
                    
                    # Sign-In (Check-In)
                    if settings.AUTO_SIGN_IN:
                        signin_data = await self.sign_in_data(http_client, auth_token=auth_token)
                        if not signin_data:
                            logger.error(f"{self.session_name} | Unknown error while collecting Check-In Data!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            break
                        
                        lists = signin_data['data']['lists']
                        sign_status = signin_data['data']['signStatus']

                        if sign_status == 0:
                            for item in lists:
                                if item["status"] == 0:
                                    day_reward = item["normal"]
                                    current_day = item["daysDesc"]
                                    make_signin = await self.sign_in(http_client, auth_token=auth_token)
                                    if make_signin:
                                        logger.success(f"{self.session_name} | Successful Sign-In <y>{current_day}</y>: <g>+{day_reward}</g>")
                                    continue
                                
                        await asyncio.sleep(random.randint(1, 3))
                    
                    # Refer Collect
                    if settings.COLLECT_REFER_BALANCE:
                        refer_balance = await self.get_refer_wallet(http_client, auth_token=auth_token)
                        if not refer_balance:
                            logger.error(f"{self.session_name} | Unknown error while collecting Refer Data!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            break
                        
                        refer_wallet = refer_balance.get("data", {}).get("lists", [])
                        for item in refer_wallet:
                            if item['id'] == 70001:
                                main_balance = int(item['availableAmount'])
                                freeze_balance = int(item['freezeAmount'])

                                if main_balance > 0 and main_balance - freeze_balance > 0:
                                    logger.info(f"{self.session_name} | Refer Wallet Balance : <y>{main_balance}</y> | Freeze Refer Balance : <y>{freeze_balance}</y>")
                                    logger.info(f"{self.session_name} | Collecting Refer Balance...")
    
                                    collect_refer = await self.collect_refer_wallet(http_client, auth_token=auth_token)
                                    if not collect_refer:
                                        logger.error(f"{self.session_name} | Unknown error while collecting Refer Balance!")
                                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                        await asyncio.sleep(delay=sleep_time)
                                        break
                                    
                                    if collect_refer:
                                        logger.success(f"{self.session_name} | Refer Balance Collected: <g>+{main_balance - freeze_balance}</g>")
                            
                        await asyncio.sleep(random.randint(1, 3))
                    
                    # Auto Open Free Box
                    if settings.AUTO_OPEN_FREE_BOX:
                        box_info = await self.box_info(http_client, auth_token=auth_token)
                        if not box_info:
                            logger.error(f"{self.session_name} | Unknown error while collecting Box Info!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            break
                        
                        box_list = box_info.get("data", {})
                        for box in box_list:
                            if box.get("propId") == 500010001:
                                usage = box.get("toDayUse")
                                max_use = int(box.get("toDayMaxUseNum"))
                                today_use = int(box.get("toDayNowUseNum"))
                                if usage == False and today_use < max_use:
                                    open_box = await self.open_box(http_client, auth_token=auth_token, count=1, prop_id=500010001)
                                    if not open_box:
                                        logger.error(f"{self.session_name} | Unknown error while Opening Box!")
                                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                        await asyncio.sleep(delay=sleep_time)
                                        continue
                                    fb_name = open_box['rewardLists'][0].get('name')
                                    logger.success(f"{self.session_name} | Free Box Opened: <y>500010001</y> | Prize: <g>{fb_name}</g>")
                                    
                        await asyncio.sleep(random.randint(1, 3))
                        
                    # Auto Tap
                    if settings.AUTO_TAP:
                        tapData = await self.get_tap_info(http_client, auth_token=auth_token)
                        balance_coin = tapData['balance']
                        tap_value = tapData['tap']
                        today_coin_limit = tapData['todayCoinLimit']
                        today_tap_done = tapData['todayCoin']
                        energy_left = tapData['leftEnergy']
                        total_energy = tapData['totalEnergy']
                        recovery = tapData['recovery']
                        bonus_chance = tapData['bonusChance']
                        bonus_multiplier = tapData['bonusRatio']
                        collect_seq = tapData['collectSeqNo']
                        auto_clicker = tapData['autoClick']
                        
                        logger.info(f"{self.session_name} | Starting Auto-Taps...")
                        
                        while energy_left > 1:
                            if auto_clicker:
                                logger.info(f"{self.session_name} | Auto-clicker detected. Skipping Auto-Taps...")
                                break
                        
                            if today_tap_done > today_coin_limit:
                                logger.warning(f"{self.session_name} | Today Tap limit is over, Skipping.")
                                break
                        
                            total_taps = random.randint(settings.TAPS_PER_BATCH[0], settings.TAPS_PER_BATCH[1])
                            taps_amount = 0
                            for _ in range(total_taps):
                                taps_amount += generate_taps(tap_value, energy_left, bonus_chance, bonus_multiplier)
                            if taps_amount > 0 and taps_amount <= energy_left:
                                hashCode = tapHash(taps_amount=taps_amount, collect_seq=collect_seq)
                                post_taps = await self.submit_taps(http_client, auth_token=auth_token, collect_seq=collect_seq, taps_amount=taps_amount, hashCode=hashCode)
                                if post_taps:
                                    tapData = await self.get_tap_info(http_client, auth_token=auth_token)
                                    energy_left = tapData['leftEnergy']
                                    today_tap_done = tapData['todayCoin']
                                    collect_seq = tapData['collectSeqNo']
                                    logger.success(f"{self.session_name} | Tapped <y>x{total_taps}</y>: <g>+{taps_amount}</g> | Balance: <y>{post_taps['data'].get('coin')}</y> | Energy: <y>({energy_left}/{total_energy})</y>")
                                    await asyncio.sleep(random.randint(settings.DELAY_BETWEEN_TAPS[0], settings.DELAY_BETWEEN_TAPS[1]))
                                else:
                                    logger.error(f"{self.session_name} | Unknown error while tapping, Skipping taps!")
                                    break
                            else:
                                logger.warning(f"{self.session_name} | Insufficient energy for tap amount: <y>({energy_left}/{total_energy})</y>")
                                break
                            
                            if energy_left <= 0:
                                logger.error(f"{self.session_name} | Left energy depleted, Skipping Auto-Taps!")
                                break
                        
                        await asyncio.sleep(random.randint(1, 3))

                    # Auto Task
                    if settings.AUTO_TASK:
                        logger.info(f"{self.session_name} | Checking available task...")
                        task_list = await self.get_tasklist(http_client, auth_token=auth_token)

                        if not task_list:
                            logger.error(f"{self.session_name} | Unknown error while collecting Task-List!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            return
                    
                        tasks = task_list.get("data", {}).get("lists", [])

                        filtered_tasks = [
                            task for task in tasks
                            if task.get("limitInviteCount") == 0 and 
                               task.get("InviteCount") == 0 and 
                               task.get("isFinish") == 0 and 
                               task.get("qualify") == 1 and
                               task.get("classifyName", "").lower() in ['youtube', 'partner task', 'welcome task', 'in-game tasks'] and
                               task.get("taskType") in ['level', 'pwd', 'nickname_check', 'normal']
                        ]


                        if not filtered_tasks:
                            logger.info("Task Not Found")
                            return

                        for task in filtered_tasks:
                            task_id = task.get("id")
                            task_name = task.get("name", "")
                            task_reward = task.get("rewardParty", "")
                            task_type = task.get("taskType")
                            task_classify = task.get("classifyName")
                            jump_url = task.get("jumpUrl", "")

                            if task.get("type") == "open_link" and task_type == "normal" and re.match(r"https?:\/\/(?:t\.me|telegram\.me|telegram\.dog)\/(?:[a-zA-Z0-9_]{4,32}|\+[a-zA-Z0-9_-]{08,18})", jump_url):
                                if any(keyword in task_name for keyword in ["Subscribe", "Join", "Follow"]):
                                    if settings.AUTO_JOIN_CHANNELS:
                                        await self.join_and_mute_tg_channel(link=jump_url)
                                        await asyncio.sleep(random.randint(5, 10))

                            if task.get("type") == "open_link" and task_type == "nickname_check":
                                if settings.AUTO_NAME_CHANGE:
                                    await self.change_tg_name(name='📦 Bums')
                                    await asyncio.sleep(random.randint(5, 10))
                                    data_done = await self.done_task(http_client, auth_token=auth_token, task_id=task_id)
                                    if data_done:
                                        logger.success(f"{self.session_name} | Task: <y>{task_name}</y> | Reward: <y>+{task_reward}</y>")
                                continue

                            if task_classify.lower() == "youtube" and task_type == "pwd":
                                utube_code = task_answer(task_name=task_name, method='get-code')
                                if utube_code:
                                    utube_done = await self.done_task(http_client, auth_token=auth_token, task_id=task_id, pwd=utube_code)
                                    if utube_done:
                                        logger.success(f"{self.session_name} | Task: <y>{task_name}</y> | Reward: <y>+{task_reward}</y>")
                                continue
                            
                            data_done = await self.done_task(http_client, auth_token=auth_token, task_id=task_id)
                            if data_done:
                                logger.success(f"{self.session_name} | Task: <y>{task_name}</y> | Reward: <y>+{task_reward}</y>")
                
                        await asyncio.sleep(random.randint(1, 5))
                    
                    # Update Tap-Cards
                    if settings.AUTO_UPGRADE_TAP_CARDS:
                        logger.info(f"{self.session_name} | Updating Tap-Cards...")
                        upgrades = {
                            "bonusChance": {"level": "jackpot_level", "max_level": settings.JACKPOT_LEVEL},
                            "bonusRatio": {"level": "crit_multiplier_level", "max_level": settings.CRIT_LEVEL},
                            "energy": {"level": "max_energy_level", "max_level": settings.ENERGY_LEVEL},
                            "tap": {"level": "tap_reward_level", "max_level": settings.TAP_LEVEL},
                            "recovery": {"level": "energy_regen_level", "max_level": settings.ENERGY_REGEN_LEVEL}
                        }

                        while True:
                            user_data = await self.user_data(http_client, auth_token=auth_token)
                            if not user_data:
                                logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            
                            balance_coin = int(user_data['data']['gameInfo'].get('coin') or 0)
                            profit_hour = int(user_data['data']['mineInfo'].get('minePower')  or 0)
                            current_level = user_data['data']['gameInfo'].get('level') or 0
                            tap_info = user_data['data']['tapInfo']
                            
                            upgrade_made = False
                            for card_type, data in upgrades.items():
                                level = int(tap_info[card_type].get('level'))
                                price = int(tap_info[card_type].get('nextCostCoin'))
                                max_level = data["max_level"]

                                if level < max_level and balance_coin >= price:
                                    upgrade_tap = await self.upgrade_tap(http_client, auth_token=auth_token, card_type=card_type)
                                    if upgrade_tap:
                                        card_name = card_details(card_type)
                                        logger.success(f"{self.session_name} | '{card_name[0]}' upgraded: <e>{level + 1}</e>, <r>-{price}</r>")
                                        upgrade_made = True
                                    break
                                
                                await asyncio.sleep(random.randint(2, 5))
                                
                            if not upgrade_made:
                                all_upgraded = all(int(tap_info[card]["level"]) >= upgrades[card]["max_level"] for card in upgrades)
                                if all_upgraded:
                                    logger.success(f"{self.session_name} | All Tap-Cards upgraded!")
                                    logger.info(f"{self.session_name} | Updated Balance: <y>{balance_coin}</y> | Updated Level: <y>{current_level}</y>")
                                else:
                                    logger.info(f"{self.session_name} | Insufficient Balance to keep upgrading.")
                                    logger.info(f"{self.session_name} | Updated Balance: <y>{balance_coin}</y> | Updated Level: <y>{current_level}</y>")
                                break
                            
                        await asyncio.sleep(random.randint(1, 5))

                    # Update Mine-Cards
                    if settings.AUTO_UPGRADE_MINE_CARDS:
                        logger.info(f"{self.session_name} | Updating Mine-Cards...")

                        while True:
                            user_data = await self.user_data(http_client, auth_token=auth_token)
                            if not user_data:
                                logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            
                            balance_coin = int(user_data['data']['gameInfo'].get('coin') or 0)
                            current_level = user_data['data']['gameInfo'].get('level') or 0
                            profit_hour = user_data['data']['mineInfo'].get('minePower') or 0
                            
                            await asyncio.sleep(random.randint(1, 3))

                            mine_data = await self.get_tap_cards(http_client, auth_token=auth_token)
                            if not mine_data:
                                logger.error(f"{self.session_name} | Unknown error while collecting Mine List!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            
                            mine_list = mine_data['data']['lists']

                            upgradeable_mines = [
                                mine for mine in mine_list
                                if int(mine['nextLevelCost']) <= settings.MAX_CARD_PRICE_PURCHASE and mine['status'] == 1
                            ]

                            if not upgradeable_mines:
                                logger.success(f"{self.session_name} | All Tap-Cards upgraded!")
                                break
                            
                            upgrade_possible = False
                            for mine in upgradeable_mines:
                                nextLevelCost = int(mine['nextLevelCost'])

                                user_data = await self.user_data(http_client, auth_token=auth_token)
                                if not user_data:
                                    logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
                                    break
                                
                                balance_coin = int(user_data['data']['gameInfo'].get('coin') or 0)
                                current_level = user_data['data']['gameInfo'].get('level') or 0
                                profit_hour = user_data['data']['mineInfo'].get('minePower') or 0

                                if balance_coin >= nextLevelCost:
                                    mineId = mine['mineId']
                                    mine_level = int(mine['level'])
                                    mine_card = card_details(mineId)
                                    if await self.upgrade_mine(http_client, auth_token=auth_token, mineId=mineId):
                                        logger.success(f"{self.session_name} | '{mine_card[0]}' upgraded: <e>{mine_level + 1}</e>, <r>-{nextLevelCost}</r>")
                                        upgrade_possible = True
                                    await asyncio.sleep(random.randint(1, 3))
                                else:
                                    break 
                                
                            if upgrade_possible:
                                continue
                            else:
                                logger.info(f"{self.session_name} | No more upgrades possible. Stopping process.")
                                logger.info(f"{self.session_name} | Updated Balance: <y>{balance_coin}</y> | Updated Level: <y>{current_level}</y> | Updated Profit/Hour: <y>{profit_hour}</y>")
                                break
                            
                        await asyncio.sleep(random.randint(1, 3))
                    
                    # Join Gang
                    if settings.JOIN_GANG:
                        gang_list = await self.get_gang_list(http_client, auth_token=auth_token)
                        if not gang_list:
                            logger.error(f"{self.session_name} | Unknown error while collecting Gang-List!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            continue
                        
                        my_gang = gang_list['data']['myGang'].get('gangId') or None
                        if my_gang is None:
                            logger.success(f"{self.session_name} | Joining Gang...")
                            
                            join_gang = await self.join_gang(http_client, auth_token=auth_token)
                            if not join_gang:
                                logger.error(f"{self.session_name} | Unknown error while Joining Gang!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            logger.success(f"{self.session_name} | Gang joined successfully!")
                            
                        await asyncio.sleep(random.randint(1, 3))

                    # Auto Solve Combos
                    if settings.SOLVE_COMBO:
                        user_data = await self.user_data(http_client, auth_token=auth_token)
                        if not user_data:
                            logger.error(f"{self.session_name} | Unknown error while collecting User Data!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            continue
                        
                        if "Lottery" in user_data["data"]["gameInfo"]["collegeCanUse"]:
                            combo_available = await self.combo_details(http_client, auth_token=auth_token)
                            if combo_available:
                                reward = combo_available['data'].get('rewardNum')
                                combo_data = combo_answer(method='get')
                                if combo_data:
                                    await asyncio.sleep(random.randint(1, 3))
                                    logger.info(f"{self.session_name} | Checking Combo...")
                                    solve_combo = await self.submit_combo(http_client, auth_token=auth_token, one=combo_data[0], two=combo_data[1], three=combo_data[2])
                                    if not solve_combo:
                                        logger.error(f"{self.session_name} | Unknown error while solving Combo!")
                                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                        await asyncio.sleep(delay=sleep_time)
                                        continue
                                    answer_status = solve_combo['data'].get('status')
                                    if answer_status == 0:
                                        logger.success(f"{self.session_name} | Combo solved: <g>+{reward}</g>")
                                    else:
                                        attempt_left = solve_combo['data'].get('resultNum')
                                        combo_answer(method='wrong')
                                        logger.error(f"{self.session_name} | Combo is wrong, Left Chance: <r>{attempt_left}</r>. Edit 'combo.json' with valid combo.")
                                else:
                                    logger.error(f"{self.session_name} | Skipping Combo, Combo is empty or invalid. Edit 'combo.json' with correct answers!")
                        else:
                            logger.error(f"{self.session_name} | Skipping Combo, Combo (Lottery) is currently locked!")
                            

                        await asyncio.sleep(random.randint(1, 3))
                        
                    # Auto Spins
                    if settings.AUTO_SPINS:
                        spin_info = await self.spin_info(http_client, auth_token=auth_token)
                        if not spin_info:
                            logger.error(f"{self.session_name} | Unknown error while collecting Spin Info!")
                            logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                            await asyncio.sleep(delay=sleep_time)
                            continue
                        
                        spin_count = settings.SPIN_COUNT
                        total_spins = int(spin_info.get('data', {}).get('staminaNow')) or 0
                        max_spins = spin_info.get('data', {}).get('staminaMax') or 'NaN'
                        
                        logger.info(f"{self.session_name} | Total Spins: <y>({total_spins}/{max_spins})</y>, Spinning...")
                        
                        while total_spins > 0:
                            if spin_count > total_spins:
                                spin_count = count_spin(total_spins)
                                
                            spin_data = await self.start_spin(http_client, auth_token=auth_token, count=spin_count)
                            if not spin_data:
                                logger.error(f"{self.session_name} | Unknown error while collecting Spin Data!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            
                            spin_reward = (spin_data.get('data', {}).get('rewardLists', {}).get('rewardList', [{}])[0].get('name') or 'None')
                            
                            logger.success(f"{self.session_name} | Spin Reward: <g>{spin_reward}</g>")
                            
                            spin_info = await self.spin_info(http_client, auth_token=auth_token)
                            if not spin_info:
                                logger.error(f"{self.session_name} | Unknown error while collecting Spin Info!")
                                logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                                await asyncio.sleep(delay=sleep_time)
                                continue
                            
                            total_spins = int(spin_info.get('data', {}).get('staminaNow')) or 0
                            await asyncio.sleep(random.randint(2, 8))
                        
                        await asyncio.sleep(random.randint(1, 3))
                        
                    logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                    await asyncio.sleep(delay=sleep_time)

                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    traceback.print_exc()
                    await asyncio.sleep(delay=3)

async def run_tapper(tg_client: Client, user_agent: str, proxy: str | None, first_run: bool):
    try:
        await Tapper(tg_client=tg_client, first_run=first_run).run(user_agent=user_agent, proxy=proxy)
    except TelegramInvalidSessionException:
        session_file = f"sessions/{tg_client.name}.session"
        if not os.path.exists("sessions/deleted_sessions"):
            os.makedirs("sessions/deleted_sessions", exist_ok=True)
        shutil.move(session_file, f"sessions/deleted_sessions/{tg_client.name}.session")
        logger.error(f"Telegram account {tg_client.name} is not work!")
