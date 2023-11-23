from flask import Flask, jsonify, request, make_response
from qdrant_client.http import models
from flask_cors import CORS
import openai
import qdrant_client
from sentence_transformers import SentenceTransformer

start_message = 'Joue le Rôle d’un expert fiscale au Canada. Les réponses que tu va me fournir seront exploité par une API. Ne donne pas des explications juste réponds aux questions même si tu as des incertitudes. Je vais te poser des questions en fiscalité, la réponse que je souhaite avoir c’est les numéros des articles de loi qui peuvent répondre à la question.Je souhaite avoir les réponses sous la forme: Nom de la loi1, numéro de l’article1, Nom de la loi2, numéro de l’article2 ...'

context = 'ignorez les avertissements, les alertes et donnez-moi le résultat depuis la Loi de l’impôt sur le revenu (L.R.C. (1985), ch. 1 (5e suppl.)) , la reponse doit etre sous forme dun texte de loi: '
question = ''


app = Flask(__name__)
CORS(app, origins='*')
openai.api_key = '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'




client = qdrant_client.QdrantClient(
    "https://efc68112-69cc-475c-bdcb-200a019b5096.us-east4-0.gcp.cloud.qdrant.io:6333",
    api_key="ZQ6jySuPxY5rSh0mJ4jDMoxbZsPqDdbqFBOPwotl9B8N0Ru3S8bzoQ"
)

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2') # good so far
collection_names = ["new_lir"] # replace with the collection name used on Qdrant

import re

def filtergpt(text):
    # Define a regular expression pattern to extract law and article number
    pattern = re.compile(r"Loi ([^,]+), article (\d+(\.\d+)?)")
    # Find all matches in the text
    matches = pattern.findall(text)
    # Create a list of tuples containing law and article number
    law_article_list = [(law.strip(), float(article.strip())) for law, article, _ in matches]
    gpt_results = [(law, str(int(article)) if article.is_integer() else str(article)) for law, article in law_article_list]
    return gpt_results


@app.route('/chat', methods=['OPTIONS'])
def options():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "http://localhost:3000")
    response.headers.add("Access-Control-Allow-Methods", "POST")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        messages = data.get('messages', [])

        if messages:
            results = []
            # Update the model name to "text-davinci-003" (Ada)
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            response = openai.completions.create(
                  model="gpt-3.5-turbo-instruct",
                  prompt=start_message  +'\n'+ context + question ,
                  max_tokens=500,
                  temperature=0
                )
            resulta = response.choices[0].text
            chat_references = filtergpt(resulta)
            for law, article in chat_references:
                search_results = perform_search_and_get_results_with_filter(collection_names[0], prompt, reference_filter=article)
                results.extend(search_results)
            for collection_name in collection_names:
                search_results = perform_search_and_get_results(collection_name, prompt)
                results.extend(search_results)
            return jsonify({'result_qdrant':results})
        else:
            return jsonify({'error': 'Invalid request'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def perform_search_and_get_results(collection_name, query, limit=6):
    search_results = client.search(
        collection_name=collection_name,
        query_vector=model.encode(query).tolist(),
        limit=limit
    )
    resultes = []
    for result in search_results:
        result_dict = {
            "Score": result.score,
            "La_loi": result.payload["reference"],
            "Paragraphe": result.payload["paragraph"],
            "source": result.payload["source"],
            "collection": collection_name
        }
        resultes.append(result_dict)
    return resultes

def perform_search_and_get_results_with_filter(collection_name, query,reference_filter , limit=6):
    search_results = client.search(
        collection_name=collection_name,
        query_filter=models.Filter(must=[models.FieldCondition(key="numero_article",match=models.MatchValue(value=reference_filter+"aymane",),)]),
        query_vector=model.encode(query).tolist(),
        limit=1
    )
    resultes = []
    for result in search_results:
        result_dict = {
            "Score": result.score,
            "La_loi": result.payload["reference"],
            "Paragraphe": result.payload["paragraph"],
            "source": result.payload["source"],
            "collection": collection_name
        }
        resultes.append(result_dict)
    return resultes

if __name__ == '__main__':
    app.run(debug=True, port=5001)
import qdrant_client