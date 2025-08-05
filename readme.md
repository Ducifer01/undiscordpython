# Undiscord.py

Uma biblioteca Python assíncrona para gerenciar e limpar mensagens em canais de DM do Discord, focada em eficiência e tratamento robusto de `rate limits`.

## Funcionalidades

- Exclusão eficiente de mensagens em canais de DM.
- Tratamento automático de `rate limits` do Discord.
- Validação de token e acesso ao canal.
- Suporte a callbacks de progresso para monitoramento.

## Instalação

Certifique-se de ter o Python 3.7+ instalado. Você pode instalar as dependências necessárias usando pip:

```bash
pip install aiohttp
```

## Como Usar

### Inicialização

Para usar a biblioteca, crie uma instância da classe `Undiscord`:

```python
from undiscordpython import Undiscord

# Opcional: configure atrasos personalizados para busca e exclusão de mensagens (em milissegundos)
# e o número máximo de tentativas para exclusão de mensagens.
undiscord = Undiscord(search_delay=1000, delete_delay=1000, max_attempts=3)
```

### Limpando Mensagens de um Canal de DM

Use o método `clear_channel` para iniciar o processo de exclusão de mensagens. Este método é assíncrono e deve ser chamado dentro de uma função `async`.

```python
import asyncio

async def main():
    user_id = "SEU_USER_ID"  # Seu ID de usuário do Discord
    token = "SEU_TOKEN_DE_USUARIO"  # Seu token de autenticação do Discord
    channel_id = "ID_DO_CANAL_DM"  # O ID do canal de DM a ser limpo

    def on_progress_update(progress):
        print(f"Progresso: {progress['deleted_count']} excluídas, {progress['failed_count']} falhas, {progress['total_processed']} processadas de {progress['total_found']} encontradas.")

    result = await undiscord.clear_channel(
        user_id=user_id,
        token=token,
        channel_id=channel_id,
        on_progress=on_progress_update
    )

    if result['success']:
        print(f"Limpeza concluída! Mensagens excluídas: {result['deleted_count']}, Falhas: {result['failed_count']}")
    else:
        print(f"Erro na limpeza: {result['message']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Parâmetros do `clear_channel`

- `user_id` (str): O ID do usuário cujas mensagens serão excluídas. **Importante**: Este deve ser o ID do usuário associado ao `token` fornecido.
- `token` (str): O token de autenticação do usuário do Discord. **Cuidado**: Mantenha seu token seguro e nunca o compartilhe publicamente.
- `channel_id` (str): O ID do canal de DM onde as mensagens serão limpas. Certifique-se de que é um canal de DM (tipo 1).
- `on_progress` (callable, opcional): Uma função de callback que será chamada periodicamente com o progresso da exclusão. A função receberá um dicionário com as chaves `deleted_count`, `failed_count`, `total_processed` e `total_found`.

## Retorno do `clear_channel`

O método `clear_channel` retorna um dicionário com as seguintes chaves:

- `success` (bool): `True` se a operação foi concluída com sucesso, `False` caso contrário.
- `message` (str): Uma mensagem descritiva sobre o resultado da operação.
- `deleted_count` (int): O número de mensagens excluídas com sucesso.
- `failed_count` (int): O número de mensagens que falharam ao serem excluídas.

## Tratamento de Erros e `Rate Limits`

A biblioteca inclui um `RateLimiter` interno que gerencia automaticamente os `rate limits` do Discord, pausando as operações quando necessário para evitar bloqueios. Erros de permissão, token inválido ou canal incorreto são tratados e reportados.

## Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir `issues` ou enviar `pull requests` no repositório do GitHub.

