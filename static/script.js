// Pega os elementos do HTML
const form = document.getElementById('upload-form');
const emailTexto = document.getElementById('email-texto');
const emailArquivo = document.getElementById('email-arquivo');

const divResultados = document.getElementById('resultados');
const spanCategoria = document.getElementById('categoria');
const spanSubCategoria = document.getElementById('sub_categoria');
const spanResposta = document.getElementById('resposta');

// Adiciona o "escutador" de envio no formulário
form.addEventListener('submit', async (event) => {
    // Previne o recarregamento da página
    event.preventDefault();

    const texto = emailTexto.value;
    const arquivo = emailArquivo.files[0];

    if (!texto && !arquivo) {
        alert('Por favor, insira um texto ou selecione um arquivo.');
        return;
    }

    // Mostra a caixa de resultados e o status de "processando"
    spanCategoria.textContent = 'Processando...';
    spanSubCategoria.textContent = '...';
    spanResposta.textContent = '...';
    divResultados.classList.remove('hidden'); // Mostra a caixa

    // Cria o FormData para enviar o arquivo ou texto
    const formData = new FormData();
    if (arquivo) {
        formData.append('file', arquivo);
    } else {
        formData.append('email_texto', texto);
    }

    try {
        // Envia os dados para o backend (Flask)
        const response = await fetch('/processar', {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        // Atualiza a interface com a resposta da API
        if (response.ok) {
            spanCategoria.textContent = data.categoria_principal;
            spanSubCategoria.textContent = data.sub_categoria;
            spanResposta.textContent = data.resposta_sugerida;
        } else {
            // Mostra uma mensagem de erro se a API falhar
            spanCategoria.textContent = 'Erro';
            spanSubCategoria.textContent = data.erro;
            spanResposta.textContent = '';
        }
    } catch (error) {
        // Mostra uma mensagem de erro se a rede falhar
        spanCategoria.textContent = 'Erro de conexão';
        spanSubCategoria.textContent = error.message;
        spanResposta.textContent = '';
    }
});