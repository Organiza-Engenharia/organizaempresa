"use client";
import { useState } from "react";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [code, setCode] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [message, setMessage] = useState<string>("");

  const handleUpload = async () => {
    if (!file) {
      console.log("❌ Nenhum arquivo selecionado.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("code", code);
    formData.append("email", email);

    console.log("📩 Enviando arquivo para o backend...");
    console.log("📂 Arquivo a ser enviado:", file);

    try {
      const response = await fetch("http://127.0.0.1:5000/upload", {
        method: "POST",
        body: formData,
      });

      console.log("📩 Resposta recebida do backend:", response);

      if (!response.ok) {
        console.error("❌ Erro ao processar PDF:", response.status);
        setMessage(`Erro ao processar PDF! Código: ${response.status}`);
        return;
      }

      const data = await response.json();
      console.log("📩 Resposta JSON do backend:", data);
      setMessage(data.message || "✅ PDF processado com sucesso!");
    } catch (error) {
      console.error("❌ Erro ao conectar com o backend:", error);
      setMessage("Erro ao enviar o PDF. Verifique o console.");
    }
  };

  return (
    <div className="flex flex-col items-center space-y-6 p-6">
      <h1 className="text-2xl font-bold">Envie seu PDF</h1>

      <input
        type="file"
        accept=".pdf"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
        className="border p-2"
      />

      <input
        type="text"
        placeholder="Digite seu código"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        className="border p-2"
      />

      <input
        type="email"
        placeholder="Digite seu e-mail"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="border p-2"
      />

      <button
        onClick={handleUpload}
        className="bg-blue-500 text-white p-2 rounded"
      >
        Enviar PDF
      </button>

      {message && <p className="text-red-500">{message}</p>}
    </div>
  );
}
