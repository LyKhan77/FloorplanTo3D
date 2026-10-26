# Dokumentasi Integrasi API Strata (Qwen3.8-Flash-Next)

Dokumentasi ini dibuat untuk memudahkan integrasi antara server inferensi **Strata** lokal (`192.168.2.142:8081`) dengan berbagai aplikasi internal perusahaan (Backend, AI Agent, Bot, Web App, dsb).

---

## 1. Informasi Server & Base URL

| Parameter | Nilai |
| :--- | :--- |
| **Server Host** | `192.168.2.142` |
| **Port** | `8081` |
| **OpenAI Base URL** | `http://192.168.2.142:8081/v1` |
| **Anthropic Base URL** | `http://192.168.2.142:8081` (Endpoint: `/v1/messages`) |
| **Model ID** | `qwen3.8-flash-next-iq2_xs` *(atau alias: `strata`)* |
| **API Key** | Nilai bebas (contoh: `none` atau `sk-internal-token`) |
| **Max Context Window** | 131.072 tokens (128K) |
| **Modalitas Input** | Teks & Gambar (Multimodal Vision) |

> **Catatan:** Server Strata 100% kompatibel dengan spesifikasi resmi **OpenAI Chat Completions API** dan **Anthropic Messages API**. Anda dapat menggunakan SDK resmi tanpa perlu memodifikasi library.

---

## 2. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Standar |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/chat/completions` | Percakapan, teks, streaming, tool calling | OpenAI |
| `POST` | `/v1/messages` | Percakapan & streaming gaya Claude/Anthropic | Anthropic |
| `POST` | `/v1/responses` | Endpoint percakapan stateless (Codex CLI) | OpenAI Responses |
| `GET` | `/v1/models` | Cek status & metadata model yang aktif | OpenAI |
| `GET` | `/health` | Healthcheck status server | Umum |
| `GET` | `/status` | Cek status inferensi (idle/processing/tokens) | Strata |
| `GET` | `/metrics` | Metrik utilisasi hardware & vLLM metrics | Prometheus / JSON |

---

## 3. Contoh Integrasi Aplikasi Internal

### A. cURL (HTTP Langsung)

#### Request Standar:
```bash
curl -X POST http://192.168.2.142:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.8-flash-next-iq2_xs",
    "messages": [
      {"role": "system", "content": "Anda adalah asisten data analitik internal perusahaan."},
      {"role": "user", "content": "Jelaskan cara menghitung Moving Average 7 hari."}
    ],
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

#### Request Streaming (Server-Sent Events):
```bash
curl -X POST http://192.168.2.142:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.8-flash-next-iq2_xs",
    "messages": [{"role": "user", "content": "Buatkan template email penawaran harga."}],
    "stream": true
  }'
```

---

### B. Python (Menggunakan Library `openai`)

Install SDK:
```bash
pip install openai
```

Kode integrasi:
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://192.168.2.142:8081/v1",
    api_key="none"  # Bebas diisi jika auth belum diaktifkan
)

# 1. Non-streaming request
response = client.chat.completions.create(
    model="qwen3.8-flash-next-iq2_xs",
    messages=[
        {"role": "system", "content": "Anda adalah asisten ERP internal."},
        {"role": "user", "content": "Bagaimana alur pembuatan Purchase Order (PO)?"}
    ],
    temperature=0.6,
    max_tokens=1000
)

# Output teks jawaban
print("Jawaban:", response.choices[0].message.content)

# Jika model melakukan reasoning/thinking:
if hasattr(response.choices[0].message, "reasoning_content"):
    print("Reasoning:", response.choices[0].message.reasoning_content)


# 2. Streaming request
stream = client.chat.completions.create(
    model="qwen3.8-flash-next-iq2_xs",
    messages=[{"role": "user", "content": "Tuliskan script bash untuk backup MySQL."}],
    stream=True
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
print()
```

---

### C. Node.js / TypeScript (Menggunakan Library `openai` atau `fetch`)

Install SDK:
```bash
npm install openai
```

Kode integrasi:
```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://192.168.2.142:8081/v1",
  apiKey: "none",
});

async function run() {
  const stream = await client.chat.completions.create({
    model: "qwen3.8-flash-next-iq2_xs",
    messages: [
      { role: "system", content: "Anda adalah bot asisten IT Support internal." },
      { role: "user", content: "Printer kasir tidak keluar struk, apa langkah awal pengecekan?" },
    ],
    stream: true,
  });

  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }
}

run().catch(console.error);
```

---

### D. Java / Spring Boot (`RestClient` / Spring AI)

Contoh pemanggilan menggunakan `RestClient` bawaan Spring Boot 3+:

```java
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import java.util.List;
import java.util.Map;

@Service
public class AiService {

    private final RestClient restClient;

    public AiService() {
        this.restClient = RestClient.builder()
                .baseUrl("http://192.168.2.142:8081/v1")
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    public Map<String, Object> askAI(String userPrompt) {
        Map<String, Object> requestBody = Map.of(
            "model", "qwen3.8-flash-next-iq2_xs",
            "messages", List.of(
                Map.of("role", "system", "content", "Anda asisten analitik database."),
                Map.of("role", "user", "content", userPrompt)
            ),
            "max_tokens", 800
        );

        return restClient.post()
                .uri("/chat/completions")
                .body(requestBody)
                .retrieve()
                .body(Map.class);
    }
}
```

---

### E. Golang (`net/http`)

```go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
}

func main() {
	reqBody := ChatRequest{
		Model: "qwen3.8-flash-next-iq2_xs",
		Messages: []Message{
			{Role: "user", Content: "Berikan query SQL untuk mencari 5 user teraktif bulan ini."},
		},
	}
	jsonData, _ := json.Marshal(reqBody)

	resp, err := http.Post("http://192.168.2.142:8081/v1/chat/completions", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	fmt.Println(string(body))
}
```

---

### F. PHP (`cURL`)

```php
<?php

$payload = [
    "model" => "qwen3.8-flash-next-iq2_xs",
    "messages" => [
        ["role" => "user", "content" => "Buatkan regex untuk memvalidasi nomor telepon Indonesia."]
    ],
    "max_tokens" => 500
];

$ch = curl_init('http://192.168.2.142:8081/v1/chat/completions');
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));

$response = curl_exec($ch);
curl_close($ch);

$result = json_decode($response, true);
echo $result['choices'][0]['message']['content'];
```

---

## 4. Fitur Khusus & Parameter Tingkat Lanjut

### A. Pengaturan Reasoning / Thinking Mode
Qwen3.8-Flash-Next memiliki fitur reasoning/chain-of-thought internal. Anda dapat mengatur kedalaman berpikir model melalui parameter request:

| Mode | Efek | Contoh Parameter |
| :--- | :--- | :--- |
| `none` | Tanpa proses berpikir, **jawaban paling cepat** | `"reasoning_effort": "none"` |
| `low` | Berpikir singkat (beberapa detik) | `"reasoning_effort": "low"` |
| `medium` | Berpikir standar | `"reasoning_effort": "medium"` |
| `high` | Berpikir mendalam untuk problem kompleks (default) | `"reasoning_effort": "high"` |

Contoh pemanggilan:
```bash
curl http://192.168.2.142:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.8-flash-next-iq2_xs",
    "messages": [{"role": "user", "content": "Berapa 125 * 38?"}],
    "reasoning_effort": "none"
  }'
```

### B. Tool Calling / Function Calling
Model mendukung format function calling OpenAI standar. Anda dapat mendefinisikan tools JSON schema dan model akan merespons dengan `tool_calls`.

---

## 5. Monitoring & Healthcheck

Untuk sistem pemantauan aplikasi internal (Prometheus, Grafana, atau script ping):

1. **Health Check:**
   ```bash
   curl http://192.168.2.142:8081/health
   # Respons: 200 OK {"status": "ok"}
   ```

2. **Metrics Prometheus (Kompatibel dengan vLLM & Grafana):**
   ```bash
   curl http://192.168.2.142:8081/metrics
   ```
   *Menyediakan data: GPU temp, GPU memory usage, tokens/sec, RAM usage, dsb.*

3. **Status Inferensi Realtime:**
   ```bash
   curl http://192.168.2.142:8081/status
   ```

---

## 6. Tips Integrasi Aplikasi Produksi

1. **HTTP Client Timeout:**
   * Atur client timeout minimal **60–120 detik**, terutama jika prompt yang dikirim sangat panjang (dokumen/codebase ribuan kata) atau menggunakan mode reasoning `high`.
2. **Koneksi Jaringan Internal:**
   * Pastikan server aplikasi Anda dapat menjangkau IP `192.168.2.142` pada port `8081` (port sudah terbuka dan dapat diakses dari LAN).
3. **Keep-Alive:**
   * Gunakan HTTP connection pooling (Keep-Alive) pada aplikasi backend Anda untuk mengurangi latency koneksi TCP handshake.

---

## 7. Integrasi dengan Coding Agents

Server Strata mendukung model **Qwen3.8-Flash-Next** yang memiliki kemampuan coding dan reasoning yang kuat. Server ini dapat langsung diintegrasikan ke berbagai coding agent modern di terminal maupun IDE.

### A. Pi Coding Agent (`@earendil-works/pi-coding-agent`)

Pi Agent mendukung custom provider OpenAI-compatible secara native. Cukup daftarkan server Strata di konfigurasi model Pi:

1. Buat atau edit file konfigurasi `~/.pi/agent/models.json` di mesin/laptop Anda:
   ```json
   {
     "providers": {
       "strata": {
         "baseUrl": "http://192.168.2.142:8081/v1",
         "api": "openai-completions",
         "apiKey": "none",
         "models": [
           {
             "id": "qwen3.8-flash-next-iq2_xs",
             "name": "Qwen 3.8 Flash Next (Strata Local)",
             "reasoning": true,
            "contextWindow": 131072,
             "maxTokens": 32768
           }
         ]
       }
     }
   }
   ```

2. Jalankan Pi Agent menggunakan model Strata:
   ```bash
   pi --model strata/qwen3.8-flash-next-iq2_xs
   ```
   *Atau di dalam antarmuka TUI Pi, ketik perintah `/model` lalu pilih `strata/qwen3.8-flash-next-iq2_xs`.*

---

### B. Claude Code (CLI)
Karena Strata menyediakan endpoint native Anthropic `/v1/messages`:
```bash
export ANTHROPIC_BASE_URL="http://192.168.2.142:8081"
export ANTHROPIC_API_KEY="none"
claude
```

---

### C. Aider
Aider dapat langsung disambungkan dengan flag `--openai-api-base`:
```bash
aider \
  --openai-api-base http://192.168.2.142:8081/v1 \
  --openai-api-key none \
  --model openai/qwen3.8-flash-next-iq2_xs
```

---

### D. Cursor IDE
1. Buka **Cursor Settings** > **Models**.
2. Di bagian **OpenAI API Key**, masukkan sembarang teks (misal: `none`).
3. Centang atau isi **Override OpenAI Base URL**: `http://192.168.2.142:8081/v1`.
4. Tambahkan model name: `qwen3.8-flash-next-iq2_xs` (atau `strata`).

---

### E. Continue / Cline / Roo Code (VS Code Extension)
Pilih provider **OpenAI Compatible**:
* **Base URL:** `http://192.168.2.142:8081/v1`
* **API Key:** `none`
* **Model:** `qwen3.8-flash-next-iq2_xs`


---

## 8. Best Practices Mencegah Eksekusi Terhenti (Anti-Truncation)

Pada agen coding otonom dengan reasoning mendalam (**Effort: xhigh**), berikut konfigurasi dan arsitektur terbaik yang telah diimplementasikan:

1. **Plafon Max Tokens Diperbesar ke 32K (`maxTokens: 32768`):**
   * Memberikan keleluasaan model untuk berpikir 8.000–16.000 token tanpa batas dan tetap menyisakan 16.000+ token untuk menghasilkan file kode masif dalam 1 panggilan tool (`write`/`edit`).
2. **Tanpa Batas Paksa Thinking Budget (`reasoning_budget_tokens: 0`):**
   * Mode berpikir tidak dipotong paksa di tengah jalan sehingga penalaran analitik model tetap maksimal di level tertinggi.
3. **Resilience & Auto-Recovery di Sisi Server:**
   * `"fit_max_tokens": true`: Jika context mendekati batas 128K, server otomatis memangkas output secara fleksibel alih-alih menolak request dengan HTTP 400.
   * `"reasoning_close_retry": true`: Jika model berhenti secara tak terduga saat masih di dalam blok `<think>`, server otomatis menyisipkan penutup `</think>` dan meminta model melanjutkan output jawaban/tool call.
   * `"tool_call_recovery": true`: Memastikan format JSON tool call yang sedikit melenceng dari template Jinja tetap diuraikan secara benar.
   * `"reasoning_loop_recovery": "recover"`: Mendeteksi pengulangan ide dan memulihkan alur penalaran tanpa crash.
4. **Auto-Compaction Conversation di Pi Agent:**
   * Diatur `reserveTokens: 34000` di `~/.pi/agent/settings.json` agar riwayat percakapan otomatis dirangkum sebelum menghimpit kuota output 32K.
