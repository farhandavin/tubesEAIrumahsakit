# 🏥 Hospital Enterprise Integration System

> **Mata Kuliah:** Enterprise Application Integration  
> **Tema:** Integrasi Rumah Sakit — Registrasi + Rekam Medis + Farmasi + Billing/Asuransi

Sistem integrasi enterprise rumah sakit yang menghubungkan **4 aplikasi independen** melalui **lapisan integrasi terpusat** menggunakan **RabbitMQ** sebagai message broker. Setiap sistem memiliki database, API, dan UI sendiri.

---

## 📋 Arsitektur Sistem

```
                           ┌─────────────────────┐
                           │   NGINX API GATEWAY  │
                           │     (Port 80)        │
                           └──────┬──────┬────────┘
                      ┌───────────┼──────┼───────────┐
                      │           │      │           │
               ┌──────▼──┐  ┌────▼───┐  │  ┌────────▼──┐
               │Registrasi│  │  EMR   │  │  │  Billing  │
               │ (REST/   │  │(REST/  │  │  │  (REST/   │
               │  JSON)   │  │ JSON)  │  │  │   JSON)   │
               │ :8001    │  │ :8002  │  │  │  :8004    │
               └────┬─────┘  └───┬────┘  │  └─────┬────┘
                    │            │        │        │
               ┌────▼─────┐ ┌───▼────┐   │  ┌─────▼────┐
               │PostgreSQL │ │MongoDB │   │  │PostgreSQL│
               │(registrasi│ │ (emr)  │   │  │(billing) │
               └───────────┘ └────────┘   │  └──────────┘
                                          │
                                   ┌──────▼──────┐
                                   │  Farmasi    │
                                   │ (SOAP/XML)  │
                                   │  :8003      │
                                   └──────┬──────┘
                                          │
                                   ┌──────▼──────┐
                                   │   MySQL     │
                                   │  (farmasi)  │
                                   └─────────────┘

              ┌──────────────────────────────────────┐
              │        INTEGRATION SERVICE           │
              │    (adapters, router, transformer)    │
              │             :8005                     │
              │                                      │
              │  ┌─────────────────────────────────┐ │
              │  │         RabbitMQ Broker          │ │
              │  │   Exchanges │ Queues │ DLQ       │ │
              │  │   :5672     │ :15672 (mgmt UI)   │ │
              │  └─────────────────────────────────┘ │
              └──────────────────────────────────────┘
```

---

## 🧩 Sistem & Teknologi

| Sistem | Framework | API Style | Database | Port |
|--------|-----------|-----------|----------|------|
| **Registrasi Pasien** | Python / FastAPI | REST / JSON | PostgreSQL | 8001 |
| **Rekam Medis (EMR)** | Python / FastAPI | REST / JSON | MongoDB | 8002 |
| **Farmasi** | Python / spyne | **SOAP / XML** | MySQL | 8003 |
| **Billing/Asuransi** | Python / FastAPI | REST / JSON | PostgreSQL | 8004 |
| **Integration Service** | Python / FastAPI | Internal REST + AMQP | — | 8005 |
| **API Gateway** | Nginx | Reverse Proxy | — | 80 |
| **Message Broker** | RabbitMQ | AMQP | — | 5672 / 15672 |

---

## 🔄 Enterprise Integration Patterns (EIP)

| # | Pattern | Implementasi |
|---|---------|-------------|
| 1 | **Message Channel** | Queue dedikasi: `patient.registration.integration`, `prescription.created`, `billing.insurance`, `billing.cash` |
| 2 | **Publish-Subscribe** | Exchange `patient.events` (fanout) — event registrasi dikirim ke EMR + Billing |
| 3 | **Content-Based Router** | Integration service memeriksa field `payment_type`: BPJS → `billing.insurance`, UMUM → `billing.cash` |
| 4 | **Message Translator** | Transformasi JSON ↔ XML/SOAP untuk komunikasi dengan Farmasi |
| 5 | **Canonical Data Model** | Format unified: `CanonicalPatient`, `CanonicalPrescription`, `CanonicalBillingEntry` |
| 6 | **Dead Letter Queue** | Pesan gagal masuk ke `.dlq` queue dengan mekanisme retry otomatis |

---

## 🚀 Cara Menjalankan

### Prasyarat
- Docker & Docker Compose terinstall
- Port 80, 15672 tersedia

### Langkah

```bash
# 1. Clone repository
git clone <repository-url>
cd tubes

# 2. Salin dan sesuaikan environment variables
cp .env.example .env

# 3. Jalankan seluruh sistem
docker compose up --build -d

# 4. Tunggu ~30 detik hingga semua service healthy
docker compose ps

# 5. Akses aplikasi
```

### URL Akses

| Aplikasi | URL |
|----------|-----|
| 🏥 Registrasi Pasien | http://localhost/registrasi/ |
| 📋 Rekam Medis (EMR) | http://localhost/emr/ |
| 💊 Farmasi | http://localhost/farmasi/ |
| 💰 Billing & Asuransi | http://localhost/billing/ |
| 🔗 Integration Hub | http://localhost/integration/ |
| 🐰 RabbitMQ Management | http://localhost:15672 |

---

## 📊 Alur Bisnis End-to-End

### Alur 1: Registrasi Pasien → Multi-Sistem Update

```
1. Petugas mendaftarkan pasien via UI Registrasi
2. Registrasi Service menyimpan ke PostgreSQL
3. Event "patient.registered" dipublish ke RabbitMQ (fanout exchange)
4. Integration Service menerima event:
   a. Transformasi ke format Canonical
   b. HTTP POST ke EMR → buat rekam medis kosong di MongoDB
   c. HTTP POST ke Billing → buat akun billing di PostgreSQL
```

### Alur 2: Resep Obat → Farmasi + Billing

```
1. Dokter membuat resep di UI EMR
2. EMR Service menyimpan ke MongoDB
3. Event "prescription.created" dipublish ke RabbitMQ
4. Integration Service menerima event:
   a. MESSAGE TRANSLATOR: konversi JSON → XML/SOAP
   b. Panggil SOAP endpoint Farmasi → dispense obat, update stok MySQL
   c. CONTENT-BASED ROUTER: cek payment_type
      - "BPJS" → publish ke queue "billing.insurance"
      - "UMUM" → publish ke queue "billing.cash"
5. Billing Service consume dari queue → buat entri tagihan
```

---

## 📁 Struktur Proyek

```
tubes/
├── docker-compose.yml          # Orkestrasi seluruh container
├── .env.example                # Template environment variables
├── .env                        # Environment variables (tidak di-commit)
├── README.md                   # Dokumentasi ini
├── gateway/                    # Nginx API Gateway
│   ├── Dockerfile
│   └── nginx.conf
├── rabbitmq/                   # Konfigurasi RabbitMQ
│   ├── rabbitmq.conf
│   └── definitions.json        # Pre-defined exchanges, queues, bindings
├── services/
│   ├── registrasi/             # Registrasi Pasien (REST/JSON + PostgreSQL)
│   ├── emr/                    # Rekam Medis (REST/JSON + MongoDB)
│   ├── farmasi/                # Farmasi (SOAP/XML + MySQL)
│   ├── billing/                # Billing & Asuransi (REST/JSON + PostgreSQL)
│   └── integration/            # Integration Layer (adapters, router, transformer)
└── docs/
    ├── architecture-diagram.md # Diagram arsitektur Mermaid
    └── api-schemas.md          # Skema API & contoh payload
```

---

## 🔑 Format Data per Sistem

### Registrasi (REST/JSON)
```json
{
  "nama": "Budi Santoso",
  "nik": "3201234567890001",
  "tanggal_lahir": "1990-05-15",
  "jenis_kelamin": "L",
  "alamat": "Jl. Merdeka No. 10, Bandung",
  "no_telepon": "081234567890",
  "payment_type": "BPJS"
}
```

### EMR (REST/JSON + MongoDB)
```json
{
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "diagnoses": ["Hipertensi Grade I"],
  "prescriptions": [{
    "prescription_id": "uuid",
    "doctor_name": "Dr. Siti Aminah",
    "items": [{"medicine_name": "Amlodipine 5mg", "quantity": 30, "dosage": "1x1"}]
  }]
}
```

### Farmasi (SOAP/XML)
```xml
<soap11env:Envelope xmlns:soap11env="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:tns="hospital.farmasi.soap">
  <soap11env:Body>
    <tns:dispense_medicine>
      <tns:prescription_id>uuid-123</tns:prescription_id>
      <tns:patient_id>1</tns:patient_id>
      <tns:patient_name>Budi Santoso</tns:patient_name>
      <tns:medicine_name>Amlodipine 5mg</tns:medicine_name>
      <tns:quantity>30</tns:quantity>
    </tns:dispense_medicine>
  </soap11env:Body>
</soap11env:Envelope>
```

### Billing (REST/JSON)
```json
{
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "description": "Resep obat - Amlodipine 5mg x30",
  "amount": 300000,
  "entry_type": "PRESCRIPTION",
  "payment_type": "BPJS",
  "source_system": "farmasi"
}
```

---

## 📖 API Endpoints

### Registrasi Service (:8001)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/api/patients` | Daftarkan pasien baru |
| GET | `/api/patients` | List semua pasien |
| GET | `/api/patients/{id}` | Detail pasien |
| GET | `/api/health` | Health check |

### EMR Service (:8002)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/api/records` | Buat rekam medis |
| GET | `/api/records` | List rekam medis |
| GET | `/api/records/{patient_id}` | Rekam medis pasien |
| POST | `/api/records/{patient_id}/prescriptions` | Tambah resep |
| GET | `/api/health` | Health check |

### Farmasi Service (:8003)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/soap` | SOAP endpoint (WSDL: `/soap?wsdl`) |
| GET | `/api/medicines` | List obat (convenience REST) |
| GET | `/api/dispensations` | List dispensasi |
| GET | `/api/health` | Health check |

### Billing Service (:8004)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/api/accounts` | Buat akun billing |
| GET | `/api/accounts` | List akun billing |
| GET | `/api/accounts/{patient_id}` | Akun billing pasien |
| GET | `/api/entries` | List entri billing |
| GET | `/api/health` | Health check |

### Integration Service (:8005)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/health` | Health check |
| GET | `/api/status` | Status integrasi |
| POST | `/api/test/patient-registration` | Trigger test registrasi |
| POST | `/api/test/prescription` | Trigger test resep |

---

## 🧪 Testing

```bash
# Verifikasi semua container berjalan
docker compose ps

# Cek health semua service
curl http://localhost/registrasi/api/health
curl http://localhost/emr/api/health
curl http://localhost/farmasi/api/health
curl http://localhost/billing/api/health
curl http://localhost/integration/api/health

# Cek RabbitMQ Management
# Buka http://localhost:15672 (login: hospital_admin / hospital_secret_2024)
```

---

## 👥 Pembagian Tugas Tim

| Anggota | Tanggung Jawab |
|---------|---------------|
| Anggota 1 | Registrasi Service + Billing Service + PostgreSQL setup |
| Anggota 2 | EMR Service (MongoDB) + Frontend UI semua service |
| Anggota 3 | Farmasi Service (SOAP/XML/MySQL) + Integration Service |
| Anggota 4 | Docker Compose + Nginx + RabbitMQ + DLQ + Dokumentasi + Testing |

---

## 📄 Lisensi

Proyek ini dibuat untuk keperluan akademik — UAS Mata Kuliah Enterprise Application Integration.
