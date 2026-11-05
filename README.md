# Dobu-CAM 🐾📷

Sistema de monitoramento inteligente para pets utilizando câmera em tempo real, Visão Computacional e comunicação HTTP.

## 🔗 Link do repositório

O código-fonte completo, a estrutura do projeto e as instruções de uso estão disponíveis no GitHub:

https://github.com/DobuChallenge/Dobu-Cam

## 📖 Sobre o projeto

A Dobu-CAM foi criada para ajudar responsáveis a monitorarem seus pets em ambientes internos, principalmente animais que necessitam de maior acompanhamento devido à idade, problemas de saúde ou necessidade de supervisão constante.

Muitos responsáveis se preocupam em não saber se o animal apareceu recentemente em determinado ambiente ou se está se movimentando normalmente durante o dia. Pensando nisso, o projeto busca oferecer uma forma simples e acessível de acompanhamento remoto utilizando uma webcam do notebook ou um celular com aplicativo de câmera IP.

A solução utiliza técnicas de Visão Computacional para analisar os frames da câmera em tempo real com OpenCV, identificando movimentações no ambiente e registrando quando o pet foi visto pela última vez. Essas informações são enviadas por comunicação HTTP para um backend Flask, responsável por processar os dados e atualizar um dashboard web em tempo real.

O projeto demonstra, na prática, a aplicação de tecnologias de Visão Computacional e comunicação entre dispositivos conectados, simulando um sistema inteligente de monitoramento de pets.

## 📁 Estrutura do projeto

Na integração com o mobile Sprint 4, é possível conectar uma câmera externa por IP ou usar a webcam do computador. O app seleciona a fonte em `/camera-source` e consulta `/status` e `/camera-frame`. As marcações salvas em `/configuracao` ativam a observação dos potes.

O adaptador `animal_observer.py` reutiliza o detector do projeto `petObserver/petObserver`, que deve ficar ao lado desta pasta. A API original do petObserver não foi alterada. Instale as dependências Python antes de iniciar `python backend.py`.

`bowl_monitor.py` conta uma possível interação após quatro segundos de permanência de um cão ou gato identificado na área marcada. Água e comida são separadas; sem marcação ou com os dois potes encobertos, não há contagem. A aproximação não confirma consumo. Os resultados ficam na sessão de captura e são reiniciados ao trocar a fonte ou salvar marcações.

Para conferir a lógica e a integração HTTP: `python -m unittest test_bowl_monitor test_tracking -v`. Esses testes não medem a acurácia visual com animais reais.

```text
Dobu-Cam/
├── backend.py          # Backend Flask, API HTTP e envio do dashboard
├── camera_iot.py       # Captura da câmera e detecção de movimento com OpenCV
├── dashboard.html      # Interface web para visualizar status, histórico e imagem
├── logo.png            # Logo utilizada no dashboard
├── requirements.txt    # Dependências Python do projeto
└── README.md           # Documentação do projeto
```

## ⚙️ Como funciona

```text
Webcam / Celular com câmera IP
                |
                | HTTP POST
                v
           Backend Flask
                |
                | HTTP GET
                v
           Dashboard Web
```

A câmera transmite os frames em tempo real utilizando OpenCV. Quando há movimentação detectada, o sistema considera que o pet apareceu, envia uma leitura HTTP para o backend, atualiza o horário de "Última vez visto", registra eventos de entrada e saída e atualiza automaticamente o dashboard.

## ✨ Funcionalidades

- 📷 Captura de câmera em tempo real.
- 📱 Compatibilidade com webcam, câmera USB ou câmera IP/celular.
- 👁️ Processamento de imagem com OpenCV.
- 🐾 Detecção de movimentação no ambiente.
- 🌐 Envio de dados via HTTP para o backend.
- 📊 Dashboard web atualizado em tempo real.
- 🟢 Registro de status do pet: animal ausente, presente parado ou presente se mexendo.
- 🕒 Registro de "Última vez visto".
- 📁 Histórico de eventos de entrada e saída.
- 🟩 Modo visual com caixa de detecção usando `--draw-detection`.

## 🛠️ Tecnologias utilizadas

- 🐍 Python
- 🌐 Flask
- 👁️ OpenCV
- 📡 Requests
- 💻 HTML
- 🎨 CSS
- ⚡ JavaScript
- 🔁 HTTP

## ✅ Resultados parciais

Como prova de conceito, a aplicação já consegue:

- 🎥 Capturar vídeo em tempo real a partir de webcam ou câmera IP.
- 👁️ Processar frames usando OpenCV.
- 🐾 Detectar movimentação no ambiente.
- 📡 Enviar status e frames para o backend Flask.
- 🔄 Atualizar o dashboard automaticamente.
- 📷 Exibir a imagem processada em tempo real.
- 🟢 Alternar o status entre "animal ausente", "animal presente e parado" e "animal presente e se mexendo".
- 🕒 Registrar o horário de "Última vez visto".
- 📁 Exibir histórico recente de eventos.

Atualmente, o sistema utiliza webcam e câmera IP como forma de demonstração funcional da proposta. Futuramente, o projeto poderá evoluir para utilizar câmeras dedicadas de monitoramento, identificação mais precisa de animais e dispositivos mais robustos, tornando a solução mais próxima de um sistema real de acompanhamento inteligente para pets.

## 🚀 Executando o projeto

Antes de iniciar, instale o Python pelo site oficial:

```text
https://www.python.org/downloads/
```

Durante a instalação, marque a opção:

```text
Add python.exe to PATH
```

Depois, abra um novo terminal e confirme a instalação:

```bash
python --version
```

### 1. Criar o ambiente virtual 🧪

```bash
cd C:\Dobu-Cam
python -m venv .venv
```

### 2. Ativar o ambiente virtual ⚡

No Windows:

```bash
.venv\Scripts\activate
```

### 3. Instalar as dependências 📦

```bash
python -m pip install -r requirements.txt
```

### 4. Iniciar o backend 🖥️

Abra um terminal na pasta do projeto e execute:

```bash
cd C:\Dobu-Cam
python backend.py
```

### 5. Abrir o dashboard 📊

No navegador, acesse:

```text
http://127.0.0.1:5000
```

### 6. Conectar a câmera 📷

Para usar a webcam do notebook, abra outro terminal na pasta do projeto e execute:

```bash
cd C:\Dobu-Cam
python camera_iot.py --draw-detection
```

Para usar a câmera do celular:

1. Instale um aplicativo de câmera IP no celular.
2. Conecte o celular e o computador na mesma rede Wi-Fi.
3. Inicie o servidor da câmera no aplicativo.
4. Copie a URL de vídeo exibida pelo app.
5. Execute no segundo terminal:

```bash
cd C:\Dobu-Cam
python camera_iot.py --camera http://ip_celular/video --draw-detection
```

## ⚙️ Parâmetros úteis

O arquivo `camera_iot.py` permite ajustar alguns parâmetros pela linha de comando:

```bash
python camera_iot.py --camera 0 --min-area 2500 --sensibilidade 25 --calibration-seconds 4 --intervalo 1.5 --frame-intervalo 0.8 --confirm-frames 4 --exit-frames 8 --presence-hold 60 --draw-detection
```

- `--camera`: índice da webcam ou URL da câmera IP.
- `--min-area`: área mínima para considerar movimento.
- `--sensibilidade`: limiar de diferença entre frames; valores menores detectam movimentos menores.
- `--calibration-seconds`: tempo inicial para aprender o fundo; deixe a câmera sem o animal nesse período.
- `--intervalo`: intervalo em segundos entre envios de status ao backend.
- `--frame-intervalo`: intervalo em segundos para atualizar a imagem do dashboard.
- `--confirm-frames`: quantidade de frames seguidos com movimento para confirmar detecção.
- `--exit-frames`: quantidade de frames sem presença para confirmar que o animal saiu da câmera.
- `--presence-hold`: tempo em segundos para manter o pet como presente após a última detecção de movimento.
- `--draw-detection`: desenha a caixa de detecção na imagem.
- `--show-window`: mostra também a janela local do OpenCV.

## 🎯 Resultado esperado

Ao executar o backend e a câmera, o dashboard deve mostrar:

- 📷 Imagem da câmera em tempo real.
- 🐾 Status atual do pet: ausente, parado ou se mexendo.
- 🕒 Campo "Última vez visto" atualizado quando há movimentação.
- 📁 Histórico de eventos de entrada e saída.
- 🎥 Fonte da câmera utilizada.

Caso a câmera ainda não esteja ativa, o sistema exibirá uma mensagem aguardando conexão.

## 👥 Integrantes

- Amandha Yumi Toyota Artulino - RM: 563549
- Giovanna Bardella Gomes - RM: 561439
- Erick Takeshi Nakajune - RM: 566059

## 📝 Observação

Projeto acadêmico desenvolvido para demonstração de Visão Computacional aplicada ao monitoramento inteligente de pets.
