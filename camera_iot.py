import argparse
import json
import time
from pathlib import Path

import cv2
import requests
from tracking import PresenceTracker


API_BASE_URL = "http://127.0.0.1:5000"
DEVICE_ID = "dobu-cam-real"
http_session = requests.Session()
CLASSES_ANIMAIS = {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}


def enviar_status(pet_detectado, em_movimento, movimento_brusco, nivel_movimento, origem, especie=None, quiet_seconds=0, animal_box=None):
    estado = "movimento_brusco" if pet_detectado and movimento_brusco else "em_movimento" if pet_detectado and em_movimento else "parado" if pet_detectado else "ausente"
    payload = {
        "device_id": DEVICE_ID,
        "sensor": origem,
        "moving": "1" if em_movimento else "0",
        "abrupt_movement": "1" if movimento_brusco else "0",
        "activity_state": estado,
        "confidence": round(nivel_movimento, 2),
        "species": especie or "",
        "quiet_seconds": round(quiet_seconds),
        "animal_box": json.dumps(animal_box),
    }
    try:
        http_session.post(f"{API_BASE_URL}/update/{1 if pet_detectado else 0}", data=payload, timeout=1.5)
    except requests.RequestException:
        print("Backend indisponivel para envio de status.")


def enviar_frame(frame):
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
    if not ok:
        return

    try:
        http_session.post(
            f"{API_BASE_URL}/camera-frame",
            files={"frame": ("camera.jpg", buffer.tobytes(), "image/jpeg")},
            timeout=1.5,
        )
    except requests.RequestException:
        print("Backend indisponivel para envio da imagem.")


def abrir_camera(camera):
    if str(camera).isdigit():
        indice = int(camera)
        # No Windows, o DirectShow costuma entregar uma captura mais estável.
        captura = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not captura.isOpened():
            captura = cv2.VideoCapture(indice)
    else:
        captura = cv2.VideoCapture(camera)

    captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if str(camera).isdigit():
        captura.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        captura.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        captura.set(cv2.CAP_PROP_FPS, 15)
    return captura


def detectar_por_movimento(
    camera,
    min_area,
    sensibilidade,
    segundos_calibracao,
    intervalo_envio,
    intervalo_frame,
    mostrar_janela,
    marcar_deteccao,
    frames_confirmacao,
    frames_saida,
    tempo_presenca,
    detector_animal=None,
    confianca_animal=0.45,
    video_duration=None,
):
    captura = abrir_camera(camera)

    if not captura.isOpened():
        raise RuntimeError("Nao foi possivel abrir a camera. Confira o indice ou a URL informada.")

    fundo = None
    inicio_calibracao = time.time()
    ultimo_envio = 0
    ultimo_frame_salvo = 0
    ultima_deteccao = None
    frames_com_presenca = 0
    frames_sem_presenca = 0
    frames_movimento_brusco = 0
    frame_anterior = None
    pet_presente = False
    origem = "camera-celular" if str(camera).startswith("http") else "webcam-real"
    arquivo_video = Path(str(camera)).is_file()
    if arquivo_video:
        origem = "video-exemplo"
    video_fps = captura.get(cv2.CAP_PROP_FPS) or 30
    if arquivo_video and video_duration and video_duration > 0:
        video_fps = max(1, captura.get(cv2.CAP_PROP_FRAME_COUNT) / video_duration)
    proximo_frame = time.monotonic()
    ultima_analise = 0
    ultimo_submit = 0
    inicio_repouso = None
    rastreador = PresenceTracker()
    anterior_movimento_em = 0
    movimento_ate = 0
    ultima_caixa = None

    print("Dobu-CAM real iniciada.")
    print("A imagem aparece no dashboard: http://127.0.0.1:5000")
    print('Identificando animais com o modelo do petObserver.' if detector_animal else f'Calibrando fundo por {segundos_calibracao:.1f}s.')
    print("Pressione Ctrl+C para parar.\n")

    try:
        while True:
            if arquivo_video:
                espera = proximo_frame - time.monotonic()
                if espera > 0:
                    time.sleep(espera)
                proximo_frame = max(proximo_frame + 1 / video_fps, time.monotonic())
            ok, frame = captura.read()
            if not ok:
                if arquivo_video:
                    captura.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    inicio_repouso = None
                    frames_com_presenca = frames_sem_presenca = 0
                    pet_presente = False
                    rastreador.reset()
                    frame_anterior = None
                    ultima_caixa = None
                    movimento_ate = 0
                    fundo = None
                    inicio_calibracao = time.time()
                    proximo_frame = time.monotonic()
                    continue
                print("Falha ao acessar a câmera.")
                time.sleep(1)
                continue

            frame = cv2.resize(frame, (640, 360))
            cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cinza = cv2.GaussianBlur(cinza, (5, 5) if detector_animal else (21, 21), 0)

            calibrando = detector_animal is None and time.time() - inicio_calibracao < segundos_calibracao

            if fundo is None:
                fundo = cinza.astype("float")
                if detector_animal is None:
                    continue

            if calibrando:
                cv2.accumulateWeighted(cinza, fundo, 0.25)
                if time.time() - ultimo_frame_salvo >= intervalo_frame:
                    cv2.putText(frame, "CALIBRANDO FUNDO", (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (24, 160, 88), 2)
                    enviar_frame(frame)
                    ultimo_frame_salvo = time.time()
                if mostrar_janela:
                    cv2.imshow("Dobu-CAM real", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                continue

            if not pet_presente:
                cv2.accumulateWeighted(cinza, fundo, 0.03)

            diferenca = cv2.absdiff(cinza, cv2.convertScaleAbs(fundo))
            limiar = cv2.threshold(diferenca, sensibilidade, 255, cv2.THRESH_BINARY)[1]
            limiar = cv2.erode(limiar, None, iterations=2)
            limiar = cv2.dilate(limiar, None, iterations=3)
            contornos, _ = cv2.findContours(limiar.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            maior_area = 0
            presenca_detectada = False
            especie_detectada = None
            confianca_detectada = 0.0
            caixa_animal = None
            nova_analise = True
            melhor_animal = None

            if detector_animal is not None:
                if time.monotonic() - ultimo_submit >= 0.5:
                    detector_animal.submit(frame)
                    ultimo_submit = time.monotonic()
                sequencia, analisado_em, deteccoes = detector_animal.snapshot()
                nova_analise = sequencia != ultima_analise
                ultima_analise = sequencia
                for caixa in deteccoes if time.monotonic() - analisado_em < 3 else []:
                    classe = caixa.classe
                    confianca = caixa.conf
                    if classe not in CLASSES_ANIMAIS or confianca < confianca_detectada:
                        continue
                    presenca_detectada = True
                    especie_detectada = classe
                    confianca_detectada = confianca
                    x1, y1, x2, y2 = map(int, (caixa.x1, caixa.y1, caixa.x2, caixa.y2))
                    caixa_animal = (x1, y1, x2, y2)
                    melhor_animal = caixa
                    maior_area = max(maior_area, max(0, x2 - x1) * max(0, y2 - y1))
                    if marcar_deteccao:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 145, 35), 2)
                        cv2.putText(frame, f"{classe} {confianca:.0%}", (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 145, 35), 2)

                pet_presente = rastreador.update(melhor_animal, time.monotonic(), nova_analise)
                if pet_presente and rastreador.animal is not None:
                    ultimo_animal = rastreador.animal
                    especie_detectada = ultimo_animal.classe
                    confianca_detectada = ultimo_animal.conf
                    if caixa_animal is None:
                        caixa_animal = tuple(map(int, (ultimo_animal.x1, ultimo_animal.y1, ultimo_animal.x2, ultimo_animal.y2)))

            for contorno in contornos:
                if detector_animal is not None:
                    continue
                area = cv2.contourArea(contorno)
                if area < min_area:
                    continue

                presenca_detectada = True
                maior_area = max(maior_area, area)
                if marcar_deteccao:
                    x, y, largura, altura = cv2.boundingRect(contorno)
                    cv2.rectangle(frame, (x, y), (x + largura, y + altura), (24, 160, 88), 2)

            movimento_area = 0
            if frame_anterior is not None:
                diff_movimento = cv2.absdiff(cinza, frame_anterior)
                limiar_movimento = cv2.threshold(diff_movimento, 12 if detector_animal else sensibilidade, 255, cv2.THRESH_BINARY)[1]
                limiar_movimento = cv2.erode(limiar_movimento, None, iterations=1)
                limiar_movimento = cv2.dilate(limiar_movimento, None, iterations=2)
                if detector_animal is not None:
                    mascara = limiar_movimento.copy()
                    limiar_movimento[:] = 0
                    if caixa_animal:
                        x1, y1, x2, y2 = caixa_animal
                        x1, y1 = max(0, x1), max(0, y1)
                        limiar_movimento[y1:y2, x1:x2] = mascara[y1:y2, x1:x2]
                contornos_movimento, _ = cv2.findContours(
                    limiar_movimento.copy(),
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE,
                )
                movimento_area = sum(cv2.contourArea(contorno) for contorno in contornos_movimento)
            if time.monotonic() - anterior_movimento_em >= 0.35:
                frame_anterior = cinza.copy()
                anterior_movimento_em = time.monotonic()

            if presenca_detectada and nova_analise:
                frames_com_presenca += 1
                frames_sem_presenca = 0
            elif nova_analise:
                frames_com_presenca = 0
                frames_sem_presenca += 1

            em_movimento = movimento_area >= min_area
            if detector_animal is not None:
                area_animal = max(1, (caixa_animal[2] - caixa_animal[0]) * (caixa_animal[3] - caixa_animal[1])) if caixa_animal else 1
                deslocamento = 0
                if caixa_animal and ultima_caixa and nova_analise:
                    deslocamento = abs(caixa_animal[0] - ultima_caixa[0]) + abs(caixa_animal[1] - ultima_caixa[1])
                if nova_analise:
                    ultima_caixa = caixa_animal
                if pet_presente and (movimento_area / area_animal >= 0.008 or deslocamento > 12):
                    movimento_ate = time.monotonic() + 1
                em_movimento = pet_presente and time.monotonic() < movimento_ate
            movimento_brusco = movimento_area >= min_area * 4
            frames_movimento_brusco = frames_movimento_brusco + 1 if movimento_brusco else 0
            movimento_brusco_confirmado = frames_movimento_brusco >= 2

            if detector_animal is None and frames_com_presenca >= frames_confirmacao:
                pet_presente = True
                ultima_deteccao = time.time()

            if detector_animal is None and frames_sem_presenca >= frames_saida:
                pet_presente = False

            if detector_animal is None and ultima_deteccao is not None and time.time() - ultima_deteccao > tempo_presenca:
                pet_presente = False

            if not pet_presente or em_movimento:
                inicio_repouso = None
            elif inicio_repouso is None:
                inicio_repouso = time.monotonic()
            quiet_seconds = time.monotonic() - inicio_repouso if inicio_repouso is not None else 0

            nivel_movimento = confianca_detectada if detector_animal is not None else min(0.99, max(maior_area, movimento_area) / 42000) if em_movimento else 0.05

            if not pet_presente:
                status = "PET AUSENTE"
            elif movimento_brusco_confirmado:
                status = "MOVIMENTO BRUSCO OBSERVADO"
            elif em_movimento:
                status = "PET PRESENTE E SE MEXENDO"
            else:
                status = "PET PRESENTE E PARADO"

            if time.time() - ultimo_frame_salvo >= intervalo_frame:
                enviar_frame(frame)
                ultimo_frame_salvo = time.time()

            if mostrar_janela:
                cv2.imshow("Dobu-CAM real", frame)

            if time.time() - ultimo_envio >= intervalo_envio:
                fresh_box = None
                if detector_animal is not None and melhor_animal is not None and time.monotonic() - analisado_em <= 2:
                    x1, y1, x2, y2 = (melhor_animal.x1, melhor_animal.y1, melhor_animal.x2, melhor_animal.y2)
                    fresh_box = {'x': max(0, x1 / 640), 'y': max(0, y1 / 360),
                                 'width': (min(640, x2) - max(0, x1)) / 640,
                                 'height': (min(360, y2) - max(0, y1)) / 360}
                enviar_status(pet_presente, em_movimento, movimento_brusco_confirmado, nivel_movimento, origem, especie_detectada, quiet_seconds, fresh_box)
                print(f"{status} | movimento={nivel_movimento:.2f}")
                ultimo_envio = time.time()

            if mostrar_janela and cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        print("\nDobu-CAM parada.")
    finally:
        captura.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dobu-CAM com camera real enviando dados IoT via HTTP.")
    parser.add_argument(
        "--camera",
        default="0",
        help="Indice da webcam, ex: 0, ou URL de camera IP/celular, ex: http://192.168.0.20:8080/video",
    )
    parser.add_argument("--min-area", type=int, default=2500, help="Area minima para considerar deteccao.")
    parser.add_argument("--sensibilidade", type=int, default=25, help="Limiar de diferenca entre frames. Valores menores detectam movimentos menores.")
    parser.add_argument("--calibration-seconds", type=float, default=4.0, help="Tempo inicial para aprender o fundo. Deixe a camera sem o animal nesse periodo.")
    parser.add_argument("--intervalo", type=float, default=1.5, help="Intervalo em segundos entre envios HTTP.")
    parser.add_argument("--frame-intervalo", type=float, default=0.12, help="Intervalo em segundos para atualizar a imagem do dashboard.")
    parser.add_argument("--show-window", action="store_true", help="Mostra tambem a janela do OpenCV.")
    parser.add_argument("--draw-detection", action="store_true", help="Desenha a caixa de deteccao para demonstrar Visao Computacional.")
    parser.add_argument("--confirm-frames", type=int, default=4, help="Quantidade de frames seguidos com movimento para confirmar deteccao.")
    parser.add_argument("--exit-frames", type=int, default=8, help="Quantidade de frames sem presenca para confirmar que o pet saiu da camera.")
    parser.add_argument("--presence-hold", type=float, default=60.0, help="Tempo em segundos para manter o pet como presente apos a ultima deteccao de movimento.")
    parser.add_argument("--animal-only", action="store_true", default=True, help="Usa YOLO para considerar somente animais, ignorando objetos e sombras.")
    parser.add_argument("--animal-conf", type=float, default=0.5, help="Confianca minima do YOLO para identificar um animal.")
    parser.add_argument("--model", default="yolov8n.pt", help="Modelo YOLO usado no modo animal-only.")
    parser.add_argument('--video-duration', type=float, default=None, help='Duração desejada da reprodução de um arquivo em segundos.')
    args = parser.parse_args()

    detector_animal = None
    if args.animal_only:
        try:
            from animal_observer import AnimalObserver
            detector_animal = AnimalObserver(args.model, args.animal_conf)
            print("Modo animal-only ativo: sombras e objetos não serão considerados animais.")
        except Exception as exc:
            raise RuntimeError(f"Não foi possível carregar o detector de animais: {exc}") from exc

    detectar_por_movimento(
        args.camera,
        args.min_area,
        args.sensibilidade,
        args.calibration_seconds,
        args.intervalo,
        args.frame_intervalo,
        args.show_window,
        args.draw_detection,
        args.confirm_frames,
        args.exit_frames,
        args.presence_hold,
        detector_animal,
        args.animal_conf,
        args.video_duration,
    )
