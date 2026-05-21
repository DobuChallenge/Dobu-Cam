import argparse
import time

import cv2
import requests


API_BASE_URL = "http://127.0.0.1:5000"
DEVICE_ID = "dobu-cam-real"


def enviar_status(pet_detectado, em_movimento, nivel_movimento, origem):
    estado = "em_movimento" if pet_detectado and em_movimento else "parado" if pet_detectado else "ausente"
    payload = {
        "device_id": DEVICE_ID,
        "sensor": origem,
        "moving": "1" if em_movimento else "0",
        "activity_state": estado,
        "confidence": round(nivel_movimento, 2),
    }
    try:
        requests.post(f"{API_BASE_URL}/update/{1 if pet_detectado else 0}", data=payload, timeout=1.5)
    except requests.RequestException:
        print("Backend indisponivel para envio de status.")


def enviar_frame(frame):
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
    if not ok:
        return

    try:
        requests.post(
            f"{API_BASE_URL}/camera-frame",
            files={"frame": ("camera.jpg", buffer.tobytes(), "image/jpeg")},
            timeout=1.5,
        )
    except requests.RequestException:
        print("Backend indisponivel para envio da imagem.")


def abrir_camera(camera):
    if str(camera).isdigit():
        captura = cv2.VideoCapture(int(camera))
    else:
        captura = cv2.VideoCapture(camera)

    captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
    frame_anterior = None
    pet_presente = False
    origem = "camera-celular" if str(camera).startswith("http") else "webcam-real"

    print("Dobu-CAM real iniciada.")
    print("A imagem aparece no dashboard: http://127.0.0.1:5000")
    print(f"Calibrando o fundo por {segundos_calibracao:.1f}s. Deixe a camera sem o animal nesse momento.")
    print("Pressione Ctrl+C para parar.\n")

    try:
        while True:
            ok, frame = captura.read()
            if not ok:
                print("Falha ao acessar a câmera.")
                time.sleep(1)
                continue

            frame = cv2.resize(frame, (640, 360))
            cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cinza = cv2.GaussianBlur(cinza, (21, 21), 0)

            calibrando = time.time() - inicio_calibracao < segundos_calibracao

            if fundo is None:
                fundo = cinza.astype("float")
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

            for contorno in contornos:
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
                limiar_movimento = cv2.threshold(diff_movimento, sensibilidade, 255, cv2.THRESH_BINARY)[1]
                limiar_movimento = cv2.erode(limiar_movimento, None, iterations=1)
                limiar_movimento = cv2.dilate(limiar_movimento, None, iterations=2)
                contornos_movimento, _ = cv2.findContours(
                    limiar_movimento.copy(),
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE,
                )
                movimento_area = sum(cv2.contourArea(contorno) for contorno in contornos_movimento)
            frame_anterior = cinza.copy()

            if presenca_detectada:
                frames_com_presenca += 1
                frames_sem_presenca = 0
            else:
                frames_com_presenca = 0
                frames_sem_presenca += 1

            em_movimento = movimento_area >= min_area

            if frames_com_presenca >= frames_confirmacao:
                pet_presente = True
                ultima_deteccao = time.time()

            if frames_sem_presenca >= frames_saida:
                pet_presente = False

            if ultima_deteccao is not None and time.time() - ultima_deteccao > tempo_presenca:
                pet_presente = False

            nivel_movimento = min(0.99, max(maior_area, movimento_area) / 42000) if em_movimento else 0.05

            if not pet_presente:
                status = "PET AUSENTE"
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
                enviar_status(pet_presente, em_movimento, nivel_movimento, origem)
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
    parser.add_argument("--frame-intervalo", type=float, default=0.8, help="Intervalo em segundos para atualizar a imagem do dashboard.")
    parser.add_argument("--show-window", action="store_true", help="Mostra tambem a janela do OpenCV.")
    parser.add_argument("--draw-detection", action="store_true", help="Desenha a caixa de deteccao para demonstrar Visao Computacional.")
    parser.add_argument("--confirm-frames", type=int, default=4, help="Quantidade de frames seguidos com movimento para confirmar deteccao.")
    parser.add_argument("--exit-frames", type=int, default=8, help="Quantidade de frames sem presenca para confirmar que o pet saiu da camera.")
    parser.add_argument("--presence-hold", type=float, default=60.0, help="Tempo em segundos para manter o pet como presente apos a ultima deteccao de movimento.")
    args = parser.parse_args()

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
    )
