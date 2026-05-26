# L.I.A. — Assistente de voz com ElevenLabs

Versão da Lia com voz natural via ElevenLabs. A chave de API fica **no servidor**,
nunca no navegador — então é seguro hospedar/compartilhar.

## Estrutura

```
lia_backend/
├── app.py              # servidor Flask (guarda a chave, faz a ponte com o ElevenLabs)
├── requirements.txt    # dependências
└── static/
    └── index.html      # a interface da Lia (front-end)
```

## Como rodar (local)

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

2. Defina sua chave do ElevenLabs como variável de ambiente
   (gere uma chave NOVA — nunca reutilize uma que tenha sido exposta):

   **Linux / Mac:**
   ```
   export ELEVENLABS_API_KEY="sk_sua_chave_nova_aqui"
   ```

   **Windows (cmd):**
   ```
   set ELEVENLABS_API_KEY=sk_sua_chave_nova_aqui
   ```

   **Windows (PowerShell):**
   ```
   $env:ELEVENLABS_API_KEY="sk_sua_chave_nova_aqui"
   ```

3. Rode o servidor:
   ```
   python app.py
   ```

4. Abra no navegador: **http://localhost:5000**

5. Clique uma vez na tela (a Lia te cumprimenta), escolha a voz no seletor,
   clique em TESTAR pra ouvir, e use o microfone pra conversar.

## Notas

- A chave **nunca** aparece no navegador. O front só conversa com `/api/tts` e
  `/api/voices` do seu próprio servidor.
- O visualizador de áudio e o rosto reagem à **amplitude real** da voz da Lia
  (via Web Audio API), não mais simulada.
- Se o ElevenLabs falhar ou a cota acabar, a Lia cai automaticamente na voz do
  navegador como fallback — ela não fica muda.
- Plano gratuito do ElevenLabs: ~10.000 caracteres/mês (~10 min de fala).
  Sem licença comercial no plano free.

## Hospedar online (próximo passo)

Para colocar no ar com segurança, suba em um serviço que suporte Python
(Render, Railway, Fly.io, PythonAnywhere) e configure `ELEVENLABS_API_KEY`
como variável de ambiente no painel do serviço — nunca no código.
Posso te ajudar com isso quando quiser.
