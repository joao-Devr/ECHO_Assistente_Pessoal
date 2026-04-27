"""
 __________________________________________________________________________
|                                                                          |
|           ███████╗ ██████╗██╗  ██╗ ██████╗                               |
|           ██╔════╝██╔════╝██║  ██║██╔═══██╗                              |
|           █████╗  ██║     ███████║██║   ██║                              |
|           ██╔══╝  ██║     ██╔══██║██║   ██║                              |
|           ███████╗╚██████╗██║  ██║╚██████╔╝                              |
|           ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝                               |
|                                                                          |
|   OPERADOR: João                                                         |
|   PROTOCOL: ECHO_V1                                                      |
|                                                                          |
|__________________________________________________________________________|
"""

import sys                        # Manipulação do interpretador Python (ex: sys.exit, sys.argv)
import subprocess                 # Abre processos externos (VS Code, Chrome, Explorer)
import threading                  # Permite rodar a escuta de voz em paralelo com o loop principal
import time                       # Controle de tempo (cooldown entre ativações, sleep)
import webbrowser                 # Abrir URLs no navegador padrão (não usado diretamente, mas útil para extensões futuras)
import os                         # Interação com o sistema operacional (caminhos, clear, execv)
import io                         # Manipulação de streams de bytes em memória (conversão do áudio)
import wave                       # Escrita de arquivos .wav em memória para o reconhecedor de voz
import speech_recognition as sr   # Biblioteca principal de reconhecimento de fala (Google Speech API)
import numpy as np                # Processamento numérico do áudio capturado (cálculo de volume, silêncio)
import sounddevice as sd          # Captura do microfone em tempo real como array numpy
import winsound                   # Emite beeps pelo alto-falante do Windows (feedback sonoro)
from dotenv import load_dotenv    # Carrega variáveis de ambiente de um arquivo .env externo para o processo

# ── CONFIGURAÇÃO ───────────────────────────

# Palavras que ativam o assistente — o usuário precisa dizer essa palavras para o echo reagir
ACTIVATION_WORD      = ["eco"]
# Perfis reconhecidos após a activation word — cada um dispara um conjunto diferente de ações
WORD_CONTEXT    = ["trabalhar", "estudar", "redes", "música", "atualizar"]
 
# Idioma enviado à API do Google para transcrição — garanrte melhor precisão em potuguês
VOICE_LANGUAGE  = "pt-BR"
 
# Taxa de amostragem do microfone em Hz — 44100 é qualidade padrão de CD
VOICE_SAMPLE_RATE    = 44100
 
# Duração de cada "escuta" em segundos — o microfone grava blocos de 4s por vez
VOICE_CHUNK_SEC      = 3
 
# Limiar mínimo de volume para considerar que há fala — filtra ruído ambiente
VOICE_SILENCE_THRESH = 0.01
 
# Tempo mínimo entre duas ativações consecutivas — evita o echo executar duas vezes por acidente
COOLDOWN = 5


# ── DIRETÓRIOS E PERFIS ────────────────────────────────

load_dotenv()  # carrega o .env automaticamente

# Lê cada variável do .env e armazena numa constante para uso no código

APP          = os.getenv("APP")
CHROME_PATH  = os.getenv("CHROME_PATH")
CHROME_PROFILE = os.getenv("CHROME_PROFILE")
EXPLORER_DIR = os.getenv("EXPLORER_DIR")
MUSIC_URL    = os.getenv("MUSIC_URL")

# Lista de variáveis obrigatórias — o echo não sobe se alguma estiver faltando no .env
# Evita erros silenciosos onde um caminho None causa falha somente ao executar o perfil

variaveis_necessarias = ["APP", "CHROME_PATH", "CHROME_PROFILE", "EXPLORER_DIR", "MUSIC_URL"]

for var in variaveis_necessarias:
    if not os.getenv(var):

        # Informa exatamente qual variável está faltando e encerra com código de erro
        print(f"  [❌ CONFIG] Variável '{var}' não encontrada no .env")
        sys.exit(1)


last_triggered = 0

# Lock de thread — impede que dois comandos de voz simultâneos executem ao mesmo tempo
lock = threading.Lock()

# ── FUNÇÕES DE FEEDBACK SONORO ─────────────────────────

def beep(freq=800, dur=100):
    try:
        
        winsound.Beep(freq, dur)
    except: pass

def play_startup_sound():
    beep(400, 90); beep(600, 90); beep(900, 100)
    

# ── LÓGICA DE EXECUÇÃO ──────────────────────────────────

def execute_echo(trigger_source, perfil):
    global last_triggered

    with lock:
        now = time.time()
        if now - last_triggered < COOLDOWN: return
        last_triggered = now

    print(f"\n  [⚡ SYSTEM] EXECUTANDO PROTOCOLO: {perfil.upper()}\n")
    play_startup_sound()
    

    if "trabalhar" in perfil:
         # Abre o VS Code e a pasta do projeto no Explorer simultaneamente

        subprocess.Popen(APP, shell=True) 
        subprocess.Popen(f'explorer "{EXPLORER_DIR}"', shell=True)
        print("  [📂] Workspace e Pasta inicializados.")

    elif "estudar" in perfil:
        # Abre um  portal de aluno no Chrome com o perfil específico do usuário

        url = "COLOQUE_URL_DO_SITE"
        cmd = f'"{CHROME_PATH}" --profile-directory="{CHROME_PROFILE}" "{url}"'
        subprocess.Popen(cmd, shell=True)
        print("  [🎓] Portal carregado.")
            
    elif "redes" in perfil:
        # Abre um terminal CMD e executa um scan de rede com nmap na faixa local (tem q baixar o NMAP)

        subprocess.Popen('start cmd /k "nmap -sn 192.168.1.0/24"', shell=True)
        print("  [📡] Scanner de rede ativo no Lab.")

    elif "música" in perfil:
        # Abre a playlist diretamente no Spotify via URI nativa do app
        # Ou use para abrir no navegador: webbrowser.open(MUSIC_URL)

        subprocess.Popen(f'start {MUSIC_URL}', shell=True)
        print("  [🎵] Music Stream iniciado.")
    
    elif "atualizar" in perfil:
        # Reinicia o próprio script Python — útil após editar o código sem fechar o terminal
        # os.execv substitui o processo atual pelo novo, sem criar um processo filho

        print("  [🔄] REBOOTING SYSTEM...")
        os.execv(sys.executable, ['python'] + sys.argv)

# ── ENGINE DE VOZ ───────────────────────────────────────

def numpy_to_audio_data(audio_np, sample_rate):
    audio_int16 = (audio_np * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    buf.seek(0)
    with sr.AudioFile(buf) as source:
        r = sr.Recognizer()
        return r.record(source)


def speech_detector():
    
    """
    Loop principal de escuta — roda em uma thread separada para não bloquear o programa.
    
    Fluxo completo a cada iteração:
      1. Grava VOICE_CHUNK_SEC segundos de áudio do microfone
      2. Verifica se o volume passa do limiar (filtra silêncio)
      3. Converte o áudio para o formato do speech_recognition
      4. Transcreve com a API do Google
      5. Verifica wake word + perfil no texto transcrito
      6. Dispara execute_echo em nova thread se encontrar correspondência
    """

    recognizer = sr.Recognizer()
    print("  [🔊] MONITOR: Captura de áudio inicializada.")

    # ── Calibração de ruído ambiente ──
    # Grava 2 segundos de silêncio para medir o ruído de fundo do ambiente

    print("  [⏳] CALIBRANDO RUÍDO...")
    try:
        noise = sd.rec(int(2 * VOICE_SAMPLE_RATE), samplerate=VOICE_SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()

        # Define o gate de volume: 3x a média do ruído ambiente, mas nunca abaixo do mínimo configurado
        # Isso adapta o limiar ao ambiente do usuário automaticamente
        vt = max(VOICE_SILENCE_THRESH, np.mean(np.abs(noise)) * 3)
        print(f"\n  [✅] CALIBRAÇÃO OK | GATE: {vt:.4f}\n")
        print("  [✅] SISTEMA ONLINE. BEM-VINDO, SENHOR.")
    except:
        print("  [❌] ERRO: Microfone não detectado.\n"); return

    while True:
        try:
            # 1. Captura um bloco de áudio do microfone
            audio = sd.rec(int(VOICE_CHUNK_SEC * VOICE_SAMPLE_RATE), 
                           samplerate=VOICE_SAMPLE_RATE, channels=1, dtype="float32")
            sd.wait() 
            flat = audio.flatten()

            # 2. Descarta o chunk se o volume máximo estiver abaixo do gate            
            if np.max(np.abs(flat)) < vt:
                continue
                
            # 3. Converte numpy array → AudioData (formato do speech_recognition)
            ad = numpy_to_audio_data(flat, VOICE_SAMPLE_RATE)
            
            # 4. Envia para a API do Google e recebe a transcrição em texto
            text = recognizer.recognize_google(ad, language=VOICE_LANGUAGE).lower()
            print(f'  [📡 MONITOR] Capturado: "{text}"')

            # 5. Verifica se alguma activation word está presente na transcrição
            if any(w in text for w in ACTIVATION_WORD):
                perfil_encontrado = None

                for ctx in WORD_CONTEXT:
                    if ctx in text:
                        perfil_encontrado = ctx
                        break

                if perfil_encontrado:
                     # 6. Executa em thread separada para não travar a escuta
                    threading.Thread(target=execute_echo, args=('VOZ 🎤', perfil_encontrado), daemon=True).start()
                
                # Pausa para não ouvir o som dos apps abrindo(Caso não utilize fone de ouvido)
               # time.sleep(COOLDOWN)

        except sr.UnknownValueError:
            continue

        except sr.RequestError:
            print("  ⚠️  Erro de conexão com o Google"); time.sleep(5)

        except Exception as e:
            print(f"  [❌ ERRO] {e}")
            time.sleep(1)

# ── INICIALIZAÇÃO ──────────────────────────────────────
if __name__ == "__main__":

    # Limpa o terminal antes de exibir a interface (cls no Windows, clear no Linux/Mac)
    os.system("cls" if os.name == "nt" else "clear")

     # Sequência de bipes de inicialização — indica que o sistema está carregando
    beep(400, 100); beep(600, 100); beep(900, 150); beep(1200,100)

    logo = """

                                                                          
              ███████╗ ██████╗██╗  ██╗ ██████╗                                     
              ██╔════╝██╔════╝██║  ██║██╔═══██╗                                    
              █████╗  ██║     ███████║██║   ██║                                    
              ██╔══╝  ██║     ██╔══██║██║   ██║                                    
              ███████╗╚██████╗██║  ██║╚██████╔╝                                    
              ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝                                     

"""
    print(logo)

    # Inicia a engine de voz em thread separada (daemon) para rodar em paralelo
    # sem bloquear o loop principal abaixo
    threading.Thread(target=speech_detector, daemon=True).start()

    # Loop principal — mantém o programa vivo enquanto a thread de voz roda em segundo plano
    # KeyboardInterrupt (Ctrl+C) é o único jeito de encerrar graciosamente    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n  [👋] E.C.H.O. OFFLINE. Até logo, Senhor.\n")
        sys.exit(0)