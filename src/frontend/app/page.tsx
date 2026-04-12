'use client' // Avisa o Next.js que isso roda no navegador do usuário
import { useState } from 'react'

export default function Home() {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [carregando, setCarregando] = useState(false)

  // Função que captura o arquivo quando o usuário seleciona
  const lidarComArquivo = (evento: React.ChangeEvent<HTMLInputElement>) => {
    if (evento.target.files && evento.target.files[0]) {
      setArquivo(evento.target.files[0])
    }
  }

  // A função que dispara quando clicamos em "Processar"
  const enviarParaAPI = async () => {
    if (!arquivo) return alert("Selecione um PDF primeiro!")

    setCarregando(true)

    // O FormData é o "pacote" que permite enviar arquivos via web
    const pacote = new FormData()
    pacote.append("arquivo", arquivo) // "arquivo" tem que ser o mesmo nome que o FastAPI espera

    try {
      const resposta = await fetch("http://127.0.0.1:8000/api/extrair/csv", {
        method: "POST",
        body: pacote,
      })

      if (!resposta.ok) throw new Error("Erro ao processar o arquivo")

      // A Mágica do Download via JavaScript
      // Pegamos o CSV da memória e criamos um link invisível para baixar
      const blob = await resposta.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.setAttribute("download", "extrato_limpo.csv") // Nome do arquivo final
      document.body.appendChild(link)
      link.click()
      link.remove()

    } catch (erro) {
      console.error(erro)
      alert("Putz, deu erro na comunicação com a API.")
    } finally {
      setCarregando(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-950 text-white">
      <div className="bg-gray-900 p-8 rounded-xl shadow-lg border border-gray-800 flex flex-col gap-6 max-w-md w-full text-center">
        
        <h1 className="text-2xl font-bold text-gray-100">Parse v1</h1>
        <p className="text-gray-400 text-sm">Transforme o Extrato do CNIS em planilha instantaneamente.</p>

        {/* Input de Arquivo Customizado usando Tailwind */}
        <input 
          type="file" 
          accept=".pdf" 
          onChange={lidarComArquivo}
          className="file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer text-gray-400"
        />

        <button 
          onClick={enviarParaAPI} 
          disabled={!arquivo || carregando}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white font-bold py-3 px-6 rounded-lg transition-all"
        >
          {carregando ? "Extraindo dados..." : "Gerar Planilha CSV"}
        </button>

      </div>
    </main>
  )
}