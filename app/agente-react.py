import argparse
import re
import requests
from openai import OpenAI
from sympy import sympify
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()


# --------------------------------------------------
# OPENAI - CLIENT
# --------------------------------------------------
client = OpenAI()
model = "gpt-4o-mini"


# --------------------------------------------------
# PROMPT
# --------------------------------------------------

prompt = '''
Você opera em um loop de PENSAMENTO, AÇÃO, PAUSA, OBSERVAÇÃO.
No final do loop, você produz uma Resposta.

Use o PENSAMENTO para descrever suas reflexões sobre a pergunta que lhe foi feita.
Use a AÇÃO para executar uma das ações disponíveis para você - então retorne à PAUSA.
A OBSERVAÇÃO será o resultado da execução dessas ações.

Suas ações disponíveis são:

calcular:
ex.: calcular: 4 * 7 / 3
Executa um cálculo e retorna o número - usa Python, então, certifique-se de usar a sintaxe de ponto flutuante, se necessário.

obter_custo:
ex.: obter_custo: teclado
Retorna o custo de um teclado.

obter_clima_atual:
ex.: obter_clima_atual: Brasília
Retorna a temperatura de uma cidade.

wikipedia:
ex.: wikipedia: LangChain
Retorna um resumo de uma pesquisa no Wikipedia.

Sempre procure informações no Wikipedia se tiver a oportunidade de fazê-lo.

Exemplo de sessão #1:

Pergunta: Quanto custa um monitor?
PENSAMENTO: Eu deveria verificar o custo de um monitor usando obter_custo.
AÇÃO: obter_custo: monitor
PAUSA

Você será chamado novamente com isto:

OBSERVAÇÃO: Um monitor custa R$ 799,00.

Você então gera a resposta:

RESPOSTA: Um monitor custa R$ 799,00.


Exemplo de sessão #2:

Pergunta: Qual é a capital da França?
PENSAMENTO: Eu deveria procurar a França no Wikipedia.
AÇÃO: wikipedia: França
PAUSA

Você será chamado novamente com isto:

OBSERVAÇÃO: A França é um país. A capital é Paris.

Você então gera a resposta:

RESPOSTA: A capital da França é Paris.


Exemplo de sessão #3:

Pergunta: Como está o tempo em São Paulo?
PENSAMENTO: Eu deveria obter a temperatura na cidade de São Paulo usando obter_clima_atual.
AÇÃO: obter_clima_atual: São Paulo
PAUSA

Você será chamado novamente com isto:

OBSERVAÇÃO: 21°C

Você então gera a resposta:

RESPOSTA: A temperatura atual em São Paulo é 21°C.

'''.strip()


# --------------------------------------------------
# AGENTE
# --------------------------------------------------
class Agente:
    def __init__(self, system: str = "") -> None:
        self.system: str = system
        self.mensagens: List[Dict[str, str]] = []

        if self.system:
            self.mensagens.append({"role": "system", "content": system})
    
    def __call__(self, prompt: str) -> str:
        self.mensagens.append({"role": "user", "content": prompt})
        resultado: str = self.executar()
        self.mensagens.append({"role": "assistant", "content": resultado})
        return resultado
        
    def executar(self, model: str = model, temperature: float = 0) -> str:
        completion = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=self.mensagens
        )
        return completion.choices[0].message.content
    
# --------------------------------------------------
# FERRAMENTAS - TOOLS
# --------------------------------------------------
def calcular(expressao: str) -> float:
    """
    Avalia uma expressão matemática fornecida em forma de string e retorna o resultado
    com no máximo duas casas decimais. A função utiliza a biblioteca SymPy. 

    Args:
        expressao (str): A expressão matemática a ser avaliada, por exemplo, "(2 * 10) + (3 * 15)".
    
    Returns:
        float: O resultado da expressão avaliada com no máximo duas casas decimais.
    """
    try:
        resultado = sympify(expressao).evalf()
        return round(float(resultado), 2)
    except Exception as e:
        return f"Erro: {e}"


def obter_custo(item: str) -> str:
    """
    Função que simula a chamada a uma API de uma loja fictícia.
    Retorna o custo de um item de tecnologia.

    Args:
        item (str): O nome do item de tecnologia.

    Returns:
        str: A mensagem com o preço do item ou uma mensagem genérica para outros itens.
    """
    if item == 'mouse':
        return 'Um mouse custa R$ 99,90'
    elif item == 'teclado':
        return 'Um teclado custa R$ 149,90'
    elif item == 'monitor':
        return 'Um monitor custa R$ 799,00'
    else:
        return 'Demais itens custam R$ 199,00.'


def obter_clima_atual(cidade: str) -> Optional[str]:
    """
    Obtém a temperatura atual de uma cidade usando a API do wttr.in.

    Args:
        cidade (str): O nome da cidade para a qual se deseja obter o clima.

    Returns:
        Optional[str]: Uma string formatada com a temperatura atual em Celsius.
        Retorna `None` se houver algum erro na requisição ou nos dados.
    """
    base_url = f"http://wttr.in/{cidade}?format=j1"
    response = requests.get(base_url)

    if response.status_code != 200:
        return None

    data = response.json()

    try:
        temperatura = data['current_condition'][0]['temp_C']
    except (KeyError, IndexError):
        return None

    return f"{temperatura}°C"


def wikipedia(termo_busca: str) -> Optional[str]:
    """
    Faz uma consulta à API do Wikipedia e retorna o 'snippet' do primeiro resultado encontrado.

    Args:
        termo_busca (str): O termo de busca a ser consultado na Wikipedia.

    Returns:
        Optional[str]: O snippet (trecho) do primeiro resultado encontrado. Retorna `None` se não houver resultados.
    """
    response = requests.get('https://en.wikipedia.org/w/api.php', params={
        'action': 'query',
        'list': 'search',
        'srsearch': termo_busca,
        'format': 'json'
    })
    results = response.json().get('query').get('search', [])
    
    if not results:
        return None
    return results[0]['snippet']


ferramentas = {
    'calcular': calcular,
    'obter_custo': obter_custo,
    'obter_clima_atual': obter_clima_atual,
    'wikipedia': wikipedia,
}


# --------------------------------------------------
# AUTOMATIZANDO O AGENTE
# --------------------------------------------------

# definindo um regex para encontrar a string 'AÇÃO'
acao_re = re.compile(r'^AÇÃO: (\w+): (.*)$')

def chamar_agente(pergunta: str, max_turns: int = 5) -> str:
    i: int = 0
    bot: Agente = Agente(prompt)
    proximo_prompt: str = pergunta

    while i < max_turns:
        i += 1
        resultado = bot(proximo_prompt)
        print(resultado)

        # usando a regex para analisar a resposta do Agente
        acoes = [
            acao_re.match(a) for a in resultado.split('\n') if acao_re.match(a)
        ]

        if acoes:
            acao, acao_input = acoes[0].groups()

            if acao not in ferramentas:
                raise Exception(f"Ação desconhecida: {acao}: {acao_input}")

            print(f"\033[92m -- executando --> {acao} {acao_input}\033[0m")
            observacao = ferramentas[acao](acao_input)

            print(f"\033[96mOBSERVAÇÃO:\033[0m {observacao}")
            proximo_prompt = f'OBSERVAÇÃO: {observacao}'
        else:
            return

        
 
# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chama o agente com um prompt")
    parser.add_argument("prompt", type=str, help="Texto do prompt para o agente")
    args = parser.parse_args()

    # Chamar a função 'chamar_agente' com o argumento passado via terminal
    chamar_agente(args.prompt)

