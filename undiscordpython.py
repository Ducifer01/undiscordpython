import aiohttp
import asyncio
import time
import logging

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Undiscord:
    def __init__(self, search_delay=1000, delete_delay=1000, max_attempts=2):
        self.rate_limiter = RateLimiter(search_delay, delete_delay)
        self.max_attempts = max_attempts

    async def _delete_message(self, session: aiohttp.ClientSession, headers: dict, channel_id: str, message_id: str) -> bool:
        attempt = 0
        while attempt < self.max_attempts:
            try:
                start_time = time.time()
                async with session.delete(
                    f'https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}',
                    headers=headers
                ) as resp:
                    ping = (time.time() - start_time) * 1000
                    self.rate_limiter.track_ping(ping)
                    
                    if resp.status in (200, 204):
                        self.rate_limiter.delete_count += 1
                        logger.debug(f'Mensagem {message_id} excluída com sucesso.')
                        return True
                    
                    elif resp.status == 429:
                        data = await resp.json()
                        retry_after = data.get('retry_after', 1)
                        self.rate_limiter.throttled_count += 1
                        self.rate_limiter.throttled_total_time += retry_after * 1000
                        logger.warning(f'Rate limit atingido ao excluir mensagem {message_id}. Aguardando {retry_after * 2}s. Tentativa {attempt + 1}/{self.max_attempts}')
                        await asyncio.sleep(retry_after * 2)
                        attempt += 1
                        continue
                    
                    elif resp.status in (403, 400):
                        logger.error(f'Permissão insuficiente ou requisição inválida para mensagem {message_id}. Status: {resp.status}')
                        return False
                    
                    else:
                        error_text = await resp.text()
                        logger.error(f'Erro ao apagar mensagem {message_id}: Status {resp.status}, Resposta: {error_text}')
                        return False
            except aiohttp.ClientError as e:
                logger.error(f'Exceção de cliente ao apagar mensagem {message_id}: {e}. Tentativa {attempt + 1}/{self.max_attempts}')
                attempt += 1
                await asyncio.sleep(1) # Pequeno atraso antes de tentar novamente em caso de erro de conexão
            
            except Exception as e:
                logger.error(f'Exceção inesperada ao apagar mensagem {message_id}: {e}. Tentativa {attempt + 1}/{self.max_attempts}')
                return False
        logger.error(f'Falha ao apagar mensagem {message_id} após {self.max_attempts} tentativas.')
        return False

    async def _fetch_messages(self, session: aiohttp.ClientSession, headers: dict, channel_id: str, user_id: str, offset=0):
        limit = 100
        message_ids = [] #Cria uma lista vazia onde será armazenado todas as mensagens encontradas.
        while True:
            await self.rate_limiter.wait_search()
            params = {'limit': limit}
            if offset:
                params['before'] = offset
            start_time = time.time()
            try:
                async with session.get(
                    f'https://discord.com/api/v10/channels/{channel_id}/messages',
                    headers=headers,
                    params=params
                ) as resp:
                    ping = (time.time() - start_time) * 1000
                    self.rate_limiter.track_ping(ping)
                    if resp.status == 429:
                        data = await resp.json()
                        retry_after = data.get('retry_after', 1)
                        self.rate_limiter.throttled_count += 1
                        self.rate_limiter.throttled_total_time += retry_after * 1000
                        logger.warning(f'Rate limit na busca de mensagens. Aguardando {retry_after * 2}s.')
                        await asyncio.sleep(retry_after * 2)
                        continue
                    if resp.status == 202:
                        data = await resp.json()
                        retry_after = data.get('retry_after', 1)
                        self.rate_limiter.throttled_count += 1
                        self.rate_limiter.throttled_total_time += retry_after * 1000
                        logger.warning(f'Canal não indexado. Aguardando {retry_after}s.')
                        await asyncio.sleep(retry_after)
                        continue
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f'Erro na busca de mensagens: Status {resp.status}, Resposta: {error_text}')
                        return
                    
                    messages = await resp.json()
                    
                    if not messages:
                        logger.info('Nenhuma mensagem encontrada na busca.')
                        break
                    
                    offset = messages[-1]['id']
                    
                    for message in messages:
                        if message['author']['id'] == user_id and message['type'] in (0, 6):
                            message_ids.append(message['id']) #Adiciona as mensagens na lista message_ids
            
            except aiohttp.ClientError as e:
                logger.error(f"Exceção de cliente ao buscar mensagens: {e}")
                return [] # Retorna lista vazia em caso de exceção
            
            except Exception as e:
                logger.error(f"Exceção inesperada ao buscar mensagens: {e}")
                return [] # Retorna lista vazia em caso de exceção
        return message_ids #Retorna a lista de mensagens
            


    async def clear_channel(self, user_id: str, token: str, channel_id: str, on_progress=None) -> dict:
        logger.info(f'Iniciando limpeza para user_id: {user_id} no canal: {channel_id}')

        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': token}

            # Validate token and channel access
            try:
                async with session.get('https://discord.com/api/v10/users/@me', headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f'Validação de token falhou. Status: {resp.status}, Resposta: {error_text}')
                        return {'success': False, 'message': 'Token inválido ou expirado.', 'deleted_count': 0, 'failed_count': 0}
                    
                    user_data_api = await resp.json()
                    if user_data_api['id'] != user_id:
                        logger.error(f"Token não corresponde ao user_id: esperado {user_id}, recebido {user_data_api['id']}")
                        return {'success': False, 'message': 'Erro interno: Token não corresponde ao usuário.', 'deleted_count': 0, 'failed_count': 0}

                async with session.get(f'https://discord.com/api/v10/channels/{channel_id}', headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f'Acesso ao canal falhou. Status: {resp.status}, Resposta: {error_text}')
                        return {'success': False, 'message': 'Não foi possível acessar o canal de DM. Verifique se o ID do canal está correto ou se o canal ainda existe.', 'deleted_count': 0, 'failed_count': 0}
                    
                    channel_data = await resp.json()
                    
                    if channel_data['type'] != 1:
                        logger.error(f"O ID fornecido ({channel_id}) não corresponde a um canal de DM. Tipo: {channel_data['type']}")
                        return {'success': False, 'message': 'O ID fornecido não corresponde a um canal de DM.', 'deleted_count': 0, 'failed_count': 0}
            
            except aiohttp.ClientError as e:
                logger.error(f'Erro de conexão durante a validação inicial: {e}')
                return {'success': False, 'message': f'Erro de conexão: {e}'}
            
            except Exception as e:
                logger.error(f'Erro inesperado durante a validação inicial: {e}')
                return {'success': False, 'message': f'Erro inesperado: {e}'}

            deleted_count = 0
            failed_count = 0
            total_processed = 0

            logger.info(f'Iniciando busca de mensagens no canal {channel_id} para o usuário {user_id}.')
            messages_to_delete = await self._fetch_messages(session, headers, channel_id, user_id)
            total_messages_found = len(messages_to_delete)
            logger.info(f"Encontradas {total_messages_found} mensagens para exclusão.")

            logger.info(f"Iniciando exclusão de mensagens no canal {channel_id} para o usuário {user_id}.")

            for message_id in messages_to_delete:
                total_processed += 1
                result = await self._delete_message(session, headers, channel_id, message_id)
                if result:
                    deleted_count += 1
                else:
                    failed_count += 1
                
                if on_progress and total_processed % 10 == 0:
                    on_progress({
                        "deleted_count": deleted_count,
                        "failed_count": failed_count,
                        "total_processed": total_processed,
                        "total_found": total_messages_found 
                    })

            logger.info(f"Limpeza concluída para user_id: {user_id} no canal: {channel_id}. Mensagens apagadas: {deleted_count}, Falhas: {failed_count}")
            return {"success": True, "message": "Limpeza concluída.", "deleted_count": deleted_count, "failed_count": failed_count}

class RateLimiter:
    def __init__(self, search_delay, delete_delay):
        self.search_delay = search_delay
        self.delete_delay = delete_delay
        self.throttled_count = 0
        self.throttled_total_time = 0
        self.avg_ping = 0
        self.last_ping = 0
        self.delete_count = 0

    async def wait_search(self):
        await asyncio.sleep(self.search_delay / 1000)

    async def wait_delete(self):
        await asyncio.sleep(self.delete_delay / 1000)

    def track_ping(self, ping):
        self.last_ping = ping
        self.avg_ping = self.avg_ping * 0.9 + ping * 0.1 if self.avg_ping > 0 else ping



