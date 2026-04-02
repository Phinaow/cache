# On part de la version précise que tu voulais
FROM verilator/verilator:v5.046

ENV VENV=/opt/venv

ENV PATH="${VENV}/bin:${PATH}"

# Installation des dépendances pour Cocotb
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python3 -m venv "${VENV}" && \
    pip install -r requirements.txt

WORKDIR /work

CMD ["bash"]
