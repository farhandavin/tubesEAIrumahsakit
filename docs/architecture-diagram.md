# 📐 Architecture Diagram — Hospital Integration System

## System Architecture (High-Level)

```mermaid
graph TB
    subgraph "API Gateway (Nginx :80)"
        GW["🌐 Nginx Reverse Proxy"]
    end

    subgraph "Application Services"
        REG["🏥 Registrasi<br/>FastAPI :8001<br/>REST/JSON"]
        EMR["📋 Rekam Medis<br/>FastAPI :8002<br/>REST/JSON"]
        FAR["💊 Farmasi<br/>spyne :8003<br/>SOAP/XML"]
        BIL["💰 Billing<br/>FastAPI :8004<br/>REST/JSON"]
    end

    subgraph "Databases (per service)"
        PG1[("PostgreSQL<br/>registrasi_db")]
        MDB[("MongoDB<br/>emr_db")]
        MYS[("MySQL<br/>farmasi_db")]
        PG2[("PostgreSQL<br/>billing_db")]
    end

    subgraph "Integration Layer"
        INT["🔗 Integration Service<br/>FastAPI :8005<br/>Adapters + Router + Transformer"]
        RMQ["🐰 RabbitMQ<br/>AMQP :5672<br/>Management :15672"]
    end

    GW --> REG
    GW --> EMR
    GW --> FAR
    GW --> BIL
    GW --> INT

    REG --> PG1
    EMR --> MDB
    FAR --> MYS
    BIL --> PG2

    REG -- "publish: patient.registered" --> RMQ
    EMR -- "publish: prescription.created" --> RMQ
    RMQ -- "consume" --> INT
    INT -- "REST call" --> EMR
    INT -- "SOAP/XML call" --> FAR
    INT -- "REST call" --> BIL
    INT -- "publish: billing.*" --> RMQ
    RMQ -- "consume: billing.insurance<br/>billing.cash" --> BIL

    style REG fill:#0f3460,stroke:#e94560,color:#fff
    style EMR fill:#0f3460,stroke:#e94560,color:#fff
    style FAR fill:#533483,stroke:#e94560,color:#fff
    style BIL fill:#0f3460,stroke:#e94560,color:#fff
    style INT fill:#16213e,stroke:#00d2ff,color:#fff
    style RMQ fill:#ff6600,stroke:#fff,color:#fff
    style GW fill:#1a1a2e,stroke:#e94560,color:#fff
    style PG1 fill:#336791,stroke:#fff,color:#fff
    style MDB fill:#4DB33D,stroke:#fff,color:#fff
    style MYS fill:#4479A1,stroke:#fff,color:#fff
    style PG2 fill:#336791,stroke:#fff,color:#fff
```

---

## Enterprise Integration Patterns (EIP) Applied

```mermaid
graph LR
    subgraph "EIP 1: Message Channel"
        MC1["patient.registration<br/>integration"]
        MC2["prescription.created"]
        MC3["billing.insurance"]
        MC4["billing.cash"]
    end

    subgraph "EIP 2: Publish-Subscribe"
        FE["patient.events<br/>(fanout exchange)"]
        FE --> MC1
    end

    subgraph "EIP 3: Content-Based Router"
        CBR{"payment_type?"}
        CBR -- "BPJS" --> MC3
        CBR -- "UMUM" --> MC4
    end

    subgraph "EIP 4: Message Translator"
        MT["JSON ↔ XML<br/>Transformer"]
    end

    subgraph "EIP 5: Canonical Data Model"
        CDM["CanonicalPatient<br/>CanonicalPrescription<br/>CanonicalBillingEntry"]
    end

    subgraph "EIP 6: Dead Letter Queue"
        DLQ["*.dlq queues<br/>retry mechanism"]
    end

    style FE fill:#ff6600,color:#fff
    style CBR fill:#e94560,color:#fff
    style MT fill:#533483,color:#fff
    style CDM fill:#0f3460,color:#fff
    style DLQ fill:#c70039,color:#fff
```

---

## Message Flow Detail

```mermaid
sequenceDiagram
    participant U as 👤 Petugas
    participant REG as 🏥 Registrasi
    participant RMQ as 🐰 RabbitMQ
    participant INT as 🔗 Integration
    participant EMR as 📋 EMR
    participant FAR as 💊 Farmasi
    participant BIL as 💰 Billing

    Note over U,BIL: ALUR 1: Registrasi Pasien

    U->>REG: POST /api/patients (JSON)
    REG->>REG: Save to PostgreSQL
    REG->>RMQ: publish "patient.registered"<br/>(fanout exchange)
    RMQ->>INT: consume from<br/>patient.registration.integration
    INT->>INT: Transform to CanonicalPatient
    INT->>EMR: POST /api/records (JSON)
    EMR->>EMR: Save to MongoDB
    INT->>BIL: POST /api/accounts (JSON)
    BIL->>BIL: Save to PostgreSQL

    Note over U,BIL: ALUR 2: Resep Obat

    U->>EMR: POST /records/{id}/prescriptions (JSON)
    EMR->>EMR: Save to MongoDB
    EMR->>RMQ: publish "prescription.created"
    RMQ->>INT: consume from prescription.created
    INT->>INT: Transform JSON → XML (Message Translator)
    INT->>FAR: SOAP call dispense_medicine (XML)
    FAR->>FAR: Update stock MySQL
    FAR-->>INT: SOAP response (XML)
    INT->>INT: Transform XML → JSON
    INT->>INT: Content-Based Router<br/>check payment_type
    
    alt payment_type = BPJS
        INT->>RMQ: publish to billing.insurance
    else payment_type = UMUM
        INT->>RMQ: publish to billing.cash
    end
    
    RMQ->>BIL: consume from billing queue
    BIL->>BIL: Create billing entry
```

---

## Docker Compose Container Topology

```mermaid
graph TB
    subgraph "Docker Compose Stack"
        subgraph "Network: hospital-integration-network"
            subgraph "Tier 1: Databases"
                PGR["postgres-registrasi<br/>:5432"]
                PGB["postgres-billing<br/>:5432"]
                MON["mongodb<br/>:27017"]
                MYS["mysql-farmasi<br/>:3306"]
            end

            subgraph "Tier 2: Message Broker"
                RMQ["rabbitmq<br/>:5672 / :15672"]
            end

            subgraph "Tier 3: Application Services"
                RS["registrasi-service<br/>:8001"]
                ES["emr-service<br/>:8002"]
                FS["farmasi-service<br/>:8003"]
                BS["billing-service<br/>:8004"]
                IS["integration-service<br/>:8005"]
            end

            subgraph "Tier 4: Gateway"
                NG["api-gateway<br/>:80"]
            end
        end
    end

    subgraph "Volumes (Persistent)"
        V1["postgres-registrasi-data"]
        V2["postgres-billing-data"]
        V3["mongodb-data"]
        V4["mysql-data"]
        V5["rabbitmq-data"]
    end

    RS --> PGR
    ES --> MON
    FS --> MYS
    BS --> PGB

    RS --> RMQ
    ES --> RMQ
    IS --> RMQ
    BS --> RMQ

    NG --> RS
    NG --> ES
    NG --> FS
    NG --> BS
    NG --> IS

    PGR --> V1
    PGB --> V2
    MON --> V3
    MYS --> V4
    RMQ --> V5

    style NG fill:#1a1a2e,stroke:#e94560,color:#fff
    style RMQ fill:#ff6600,stroke:#fff,color:#fff
```
