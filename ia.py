def analisar_pet(dados):
    """
    Analisa o estado atual e o histórico do pet.
    """

    pet_detectado = dados.get("pet_detected", False)
    pet_moving = dados.get("pet_moving", False)
    activity_state = dados.get("activity_state", "ausente")
    confidence = dados.get("confidence", 0.0)
    eventos = dados.get("events", [])

    quantidade_eventos = len(eventos)

    entradas = sum(
        1
        for evento in eventos
        if "voltou" in evento.get("message", "").lower()
    )

    saidas = sum(
        1
        for evento in eventos
        if "saiu" in evento.get("message", "").lower()
    )

    dados_analisados = {
        "pet_detectado": pet_detectado,
        "movimento": pet_moving,
        "estado": activity_state,
        "confianca_deteccao": confidence,
        "total_eventos": quantidade_eventos,
        "entradas": entradas,
        "saidas": saidas,
    }

    # --------------------------------------------------
    # PET AUSENTE
    # --------------------------------------------------

    if not pet_detectado:

        if quantidade_eventos >= 4:
            return {
                "nivel": "atenção",
                "titulo": "Pet atualmente ausente",
                "analise": (
                    f"O pet não está sendo detectado neste momento. "
                    f"O histórico recente possui {quantidade_eventos} eventos, "
                    f"com {entradas} entradas e {saidas} saídas da área monitorada."
                ),
                "recomendacao": (
                    "Observe o histórico para verificar se esse padrão de "
                    "ausência é comum para o pet."
                ),
                "dados_analisados": dados_analisados,
            }

        return {
            "nivel": "atenção",
            "titulo": "Pet não detectado",
            "analise": (
                "A câmera não está detectando o pet no momento. "
                "Ele pode estar fora do campo de visão da câmera."
            ),
            "recomendacao": (
                "Continue monitorando o ambiente e acompanhe os próximos eventos."
            ),
            "dados_analisados": dados_analisados,
        }

    # --------------------------------------------------
    # PET EM MOVIMENTO
    # --------------------------------------------------

    if pet_moving:

        if entradas >= 3:
            return {
                "nivel": "normal",
                "titulo": "Pet ativo",
                "analise": (
                    f"O pet está presente e apresenta movimentação. "
                    f"O histórico recente registra {entradas} entradas "
                    f"na área monitorada."
                ),
                "recomendacao": (
                    "O sistema identificou atividade recorrente. "
                    "Continue acompanhando o comportamento do pet."
                ),
                "dados_analisados": dados_analisados,
            }

        return {
            "nivel": "normal",
            "titulo": "Pet em movimento",
            "analise": (
                f"O pet foi detectado e apresenta atividade de movimento. "
                f"A confiança da detecção é de {confidence:.0%}."
            ),
            "recomendacao": (
                "Continue acompanhando o comportamento do pet "
                "pelo monitoramento."
            ),
            "dados_analisados": dados_analisados,
        }

    # --------------------------------------------------
    # PET PARADO
    # --------------------------------------------------

    if activity_state == "parado":

        return {
            "nivel": "normal",
            "titulo": "Pet detectado e parado",
            "analise": (
                "O pet está presente no ambiente, mas não apresenta "
                "movimentação no momento."
            ),
            "recomendacao": (
                "Continue monitorando o comportamento ao longo do dia "
                "para identificar mudanças no padrão de atividade."
            ),
            "dados_analisados": dados_analisados,
        }

    # --------------------------------------------------
    # SITUAÇÃO PADRÃO
    # --------------------------------------------------

    return {
        "nivel": "normal",
        "titulo": "Monitoramento ativo",
        "analise": (
            "O pet está sendo monitorado normalmente pela Dobu-CAM."
        ),
        "recomendacao": (
            "Continue acompanhando os eventos registrados."
        ),
        "dados_analisados": dados_analisados,
    }