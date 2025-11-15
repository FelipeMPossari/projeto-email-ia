from flask import Flask, request, jsonify, render_template
import os
import fitz
import json 
import string
import nltk
from nltk.corpus import stopwords
from nltk.stem import RSLPStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

API_KEY = os.environ.get("API_KEY") 

try:
    genai.configure(api_key=API_KEY)
    
    generation_config = {
      "temperature": 0.2,
      "top_p": 1,
      "top_k": 1
    }

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", 
        generation_config=generation_config
    )
    print("Modelo Gemini carregado.")

except Exception as e:
    print(f"Erro ao inicializar cliente Gemini: {e}")
    model = None

try:
    nltk.data.find('corpora/stopwords')
    nltk.data.find('stemmers/rslp')
except LookupError:
    print("Baixando pacotes NLTK (stopwords, rslp)...")
    nltk.download('stopwords', quiet=True)
    nltk.download('rslp', quiet=True)

stop_words_pt = set(stopwords.words('portuguese'))
stemmer_pt = RSLPStemmer()

vectorizer = TfidfVectorizer()
classifier = MultinomialNB()
labels_local = ["Improdutivo", "Produtivo"] 

def preprocess_text(texto):
    texto = texto.lower()
    texto = texto.translate(str.maketrans('', '', string.punctuation))
    palavras = texto.split()
    palavras_processadas = [stemmer_pt.stem(p) for p in palavras if p not in stop_words_pt]
    return " ".join(palavras_processadas)

def treinar_modelo_local():
    print("Iniciando treinamento do modelo local (roteador)...")
    try:
        with open('dataset.json', 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        
        textos = [item['texto'] for item in dataset]
        labels_num = [item['label'] for item in dataset]
        
        print(f"Processando {len(textos)} exemplos do dataset...")
        textos_processados = [preprocess_text(t) for t in textos]
        
        print("Treinando TfidfVectorizer e MultinomialNB...")
        X_tfidf = vectorizer.fit_transform(textos_processados)
        classifier.fit(X_tfidf, labels_num)
        
        print("--- Modelo local treinado e pronto! ---")
    except Exception as e:
        print(f"Erro grave ao treinar modelo local: {e}")

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def ler_pdf(file_stream):
    try:
        with fitz.open(stream=file_stream, filetype="pdf") as doc:
            texto_completo = ""
            for page in doc: texto_completo += page.get_text()
            return texto_completo
    except Exception as e: return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/processar', methods=['POST'])
def processar_email():
    
    texto_email = None
    if 'file' in request.files:
        file = request.files['file']
        if file and allowed_file(file.filename):
            extensao = file.filename.rsplit('.', 1)[1].lower()
            if extensao == 'txt': texto_email = file.read().decode('utf-8')
            elif extensao == 'pdf': texto_email = ler_pdf(file.stream.read())
    elif 'email_texto' in request.form:
        texto_email = request.form['email_texto']

    if texto_email is None:
        return jsonify({'erro': 'Nenhum texto ou arquivo válido foi enviado'}), 400

    if len(texto_email.strip()) < 5:
        return jsonify({
            'categoria_principal': 'Improdutivo',
            'sub_categoria': 'Inválido',
            'resposta_sugerida': 'O e-mail fornecido é muito curto para ser processado.'
        })

    texto_processado_local = preprocess_text(texto_email)
    X_novo = vectorizer.transform([texto_processado_local])
    predicao_num = classifier.predict(X_novo)
    categoria_local = labels_local[predicao_num[0]]
    
    print(f"--- Modelo Local: Classificou como '{categoria_local}' ---")

    if model is None:
        return jsonify({'erro': 'Cliente da Gemini não inicializado.'}), 500

    prompt_sistema_openai = f"""
    Suas tarefas são:
    1. "sub_categoria": Faça uma classificação do tipo do email.
    2. "resposta_sugerida": Gere uma resposta curta adequada ao email.
    
    Responda com um objeto JSON (ex: {{"sub_categoria": "...", "resposta_sugerida": "..."}})
    """
        
    try:
        prompt_completo = f"{prompt_sistema_openai}\n\nEmail a ser analisado: \"{texto_email}\""

        
        response = model.generate_content(
            prompt_completo
        )
        
        if not response.parts:
            print("Erro: A API do Gemini bloqueou a resposta.")
            try:
                print(f"DEBUG: Finish Reason: {response.candidates[0].finish_reason}")
            except Exception:
                pass
            return jsonify({'erro': 'A IA bloqueou esta resposta por segurança.'}), 500
        
        resposta_json_str = response.text.strip().replace("```json\n", "").replace("\n```", "")
        
        print(f"Resposta da IA (JSON): {resposta_json_str}")
        
        dados_resposta = json.loads(resposta_json_str)
        
        sub_categoria = dados_resposta.get("sub_categoria", "N/A")
        resposta_sugerida = dados_resposta.get("resposta_sugerida", "IA não forneceu resposta.")

        return jsonify({
            'categoria_principal': categoria_local,
            'sub_categoria': sub_categoria,
            'resposta_sugerida': resposta_sugerida
        })

    except Exception as e:
        print(f"Erro ao chamar a API do Gemini: {e}")
        return jsonify({'erro': f'Falha na comunicação com a IA: {str(e)}'}), 500

if not os.path.exists('dataset.json'):
    print("ERRO: 'dataset.json' não encontrado!")
    print("Por favor, crie o 'dataset.json' com os 80 exemplos antes de rodar.")
else:
    treinar_modelo_local() 

if __name__ == '__main__':
    app.run(debug=True)