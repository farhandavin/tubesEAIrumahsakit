# 📋 API & Message Schemas — Hospital Integration System

## Registrasi Pasien (REST/JSON)

### Swagger/OpenAPI
Tersedia otomatis di: `http://localhost/registrasi/docs`

### POST /api/patients — Request
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

### POST /api/patients — Response
```json
{
  "id": 1,
  "nama": "Budi Santoso",
  "nik": "3201234567890001",
  "tanggal_lahir": "1990-05-15",
  "jenis_kelamin": "L",
  "alamat": "Jl. Merdeka No. 10, Bandung",
  "no_telepon": "081234567890",
  "payment_type": "BPJS",
  "created_at": "2024-01-15T10:30:00"
}
```

---

## Rekam Medis / EMR (REST/JSON + MongoDB)

### Swagger/OpenAPI
Tersedia otomatis di: `http://localhost/emr/docs`

### POST /api/records/{patient_id}/prescriptions — Request
```json
{
  "doctor_name": "Dr. Siti Aminah",
  "diagnosis": "Hipertensi Grade I",
  "items": [
    {
      "medicine_name": "Amlodipine 5mg",
      "quantity": 30,
      "dosage": "1x1 tablet setelah makan"
    },
    {
      "medicine_name": "Paracetamol 500mg",
      "quantity": 10,
      "dosage": "3x1 tablet setelah makan"
    }
  ]
}
```

### Medical Record Document (MongoDB)
```json
{
  "_id": "ObjectId(...)",
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "diagnoses": ["Hipertensi Grade I"],
  "prescriptions": [
    {
      "prescription_id": "uuid-abc-123",
      "doctor_name": "Dr. Siti Aminah",
      "diagnosis": "Hipertensi Grade I",
      "items": [
        {"medicine_name": "Amlodipine 5mg", "quantity": 30, "dosage": "1x1"}
      ],
      "created_at": "2024-01-15T11:00:00"
    }
  ],
  "visits": [
    {"date": "2024-01-15T10:30:00", "type": "REGISTRATION"}
  ],
  "created_at": "2024-01-15T10:30:00"
}
```

---

## Farmasi (SOAP/XML + MySQL)

### WSDL
Tersedia di: `http://localhost/farmasi/soap?wsdl`

### SOAP Request — dispense_medicine
```xml
<?xml version='1.0' encoding='utf-8'?>
<soap11env:Envelope 
    xmlns:soap11env="http://schemas.xmlsoap.org/soap/envelope/" 
    xmlns:tns="hospital.farmasi.soap">
  <soap11env:Body>
    <tns:dispense_medicine>
      <tns:prescription_id>uuid-abc-123</tns:prescription_id>
      <tns:patient_id>1</tns:patient_id>
      <tns:patient_name>Budi Santoso</tns:patient_name>
      <tns:medicine_name>Amlodipine 5mg</tns:medicine_name>
      <tns:quantity>30</tns:quantity>
    </tns:dispense_medicine>
  </soap11env:Body>
</soap11env:Envelope>
```

### SOAP Response — dispense_medicine
```xml
<?xml version='1.0' encoding='utf-8'?>
<soap11env:Envelope 
    xmlns:soap11env="http://schemas.xmlsoap.org/soap/envelope/" 
    xmlns:tns="hospital.farmasi.soap">
  <soap11env:Body>
    <tns:dispense_medicineResponse>
      <tns:dispense_medicineResult>
        &lt;result&gt;
          &lt;status&gt;SUCCESS&lt;/status&gt;
          &lt;dispensation_id&gt;1&lt;/dispensation_id&gt;
          &lt;medicine_name&gt;Amlodipine 5mg&lt;/medicine_name&gt;
          &lt;quantity&gt;30&lt;/quantity&gt;
          &lt;total_price&gt;300000&lt;/total_price&gt;
          &lt;remaining_stock&gt;220&lt;/remaining_stock&gt;
        &lt;/result&gt;
      </tns:dispense_medicineResult>
    </tns:dispense_medicineResponse>
  </soap11env:Body>
</soap11env:Envelope>
```

---

## Billing & Asuransi (REST/JSON)

### Swagger/OpenAPI
Tersedia otomatis di: `http://localhost/billing/docs`

### BillingAccount Response
```json
{
  "id": 1,
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "payment_type": "BPJS",
  "status": "ACTIVE",
  "created_at": "2024-01-15T10:30:00"
}
```

### BillingEntry Response
```json
{
  "id": 1,
  "account_id": 1,
  "description": "Biaya registrasi pasien",
  "amount": 0,
  "entry_type": "REGISTRATION",
  "payment_type": "BPJS",
  "source_system": "registrasi",
  "created_at": "2024-01-15T10:30:00"
}
```

---

## Canonical Data Model (Internal Message Format)

### CanonicalPatient
```json
{
  "source_id": 1,
  "nama": "Budi Santoso",
  "nik": "3201234567890001",
  "tanggal_lahir": "1990-05-15",
  "jenis_kelamin": "L",
  "alamat": "Jl. Merdeka No. 10, Bandung",
  "no_telepon": "081234567890",
  "payment_type": "BPJS",
  "event_type": "patient.registered",
  "timestamp": "2024-01-15T10:30:00"
}
```

### CanonicalPrescription
```json
{
  "prescription_id": "uuid-abc-123",
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "doctor_name": "Dr. Siti Aminah",
  "diagnosis": "Hipertensi Grade I",
  "items": [
    {"medicine_name": "Amlodipine 5mg", "quantity": 30, "dosage": "1x1"}
  ],
  "payment_type": "BPJS",
  "event_type": "prescription.created",
  "timestamp": "2024-01-15T11:00:00"
}
```

### CanonicalBillingEntry
```json
{
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "description": "Resep obat - Amlodipine 5mg x30",
  "amount": 300000,
  "entry_type": "PRESCRIPTION",
  "payment_type": "BPJS",
  "source_system": "farmasi",
  "event_type": "billing.charge",
  "timestamp": "2024-01-15T11:00:00"
}
```

---

## RabbitMQ Exchange & Queue Topology

| Exchange | Type | Bound Queues | Routing Key |
|----------|------|-------------|-------------|
| `patient.events` | fanout | `patient.registration.integration` | — (fanout) |
| `prescription.events` | direct | `prescription.created` | `prescription.created` |
| `billing.events` | direct | `billing.insurance` | `billing.insurance` |
| `billing.events` | direct | `billing.cash` | `billing.cash` |
| `dlx.exchange` | direct | `*.dlq` queues | respective `.dlq` keys |

---

## Data Transformation Examples

### JSON → XML (Prescription to Farmasi SOAP)

**Before (JSON — from EMR):**
```json
{
  "prescription_id": "uuid-abc-123",
  "patient_id": 1,
  "patient_name": "Budi Santoso",
  "items": [
    {"medicine_name": "Amlodipine 5mg", "quantity": 30, "dosage": "1x1"}
  ]
}
```

**After (XML — to Farmasi SOAP):**
```xml
<soap11env:Envelope xmlns:soap11env="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:tns="hospital.farmasi.soap">
  <soap11env:Body>
    <tns:dispense_medicine>
      <tns:prescription_id>uuid-abc-123</tns:prescription_id>
      <tns:patient_id>1</tns:patient_id>
      <tns:patient_name>Budi Santoso</tns:patient_name>
      <tns:medicine_name>Amlodipine 5mg</tns:medicine_name>
      <tns:quantity>30</tns:quantity>
    </tns:dispense_medicine>
  </soap11env:Body>
</soap11env:Envelope>
```

### Content-Based Routing Example

**Input message:**
```json
{
  "patient_id": 1,
  "payment_type": "BPJS",
  "amount": 300000,
  "entry_type": "PRESCRIPTION"
}
```

**Routing decision:**
- `payment_type == "BPJS"` → Route to queue `billing.insurance`
- `payment_type == "UMUM"` → Route to queue `billing.cash`
