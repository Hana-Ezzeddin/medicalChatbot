import re
import pandas as pd
from textblob import TextBlob
from nltk.corpus import stopwords
from experta import *
import nltk

def load_knowledge_base(csv_path):
    df=pd.read_csv(csv_path)
    df=df.dropna()
    kb={}
    for _, row in df.iterrows():
        disease=row["disease"].strip()
        symptoms={s.strip() for s in row["symptoms"].split(",")}
        precautions=[p.strip() for p in row["precautions"].split(",")]
        if disease not in kb:
            kb[disease]={"symptoms": set(), "precautions": precautions}
        kb[disease]["symptoms"].update(symptoms)
    return kb

stopword= stopwords.words('english')
def remove_stopwords(text):
    new_text= []
    for word in text.split():
        if word in stopword:
            new_text.append('')
        else:
            new_text.append(word)
    x = new_text[:]
    new_text.clear()
    return " ".join(x)

def preprocess(text):   #Lowercase ,misspellings, remove stopwords and tokenise 
    text=text.lower()
    text=remove_stopwords(text)
    text = str(TextBlob(text).correct())
    text=re.sub(r"[^a-z\s]", " ", text)
    return text.split()

def extract_symptoms(user_text, all_symptoms):
    words=preprocess(user_text)
    user_phrase=" ".join(words)
    matched= set()
    for sym in all_symptoms:
        readable = sym.replace("_", " ")
        parts = readable.split()
        if readable in user_phrase or set(parts).issubset(words):            
            matched.add(sym)
    return list(matched)

def process_sym(sym):
    s= sym.replace("_", " ").replace("  ", " ").title()
    return s

def main():
    csv_path= r"D:\cogProj\Medical Diagnosis Expert System.csv"
    kb=load_knowledge_base(csv_path)
    
    all_symptoms= set()
    for d in kb:
        all_symptoms.update(kb[d]["symptoms"])

    print("Welcome to the Medical Diagnosis Expert System!")
    user_input=input("Enter your symptoms: ")
    matched=extract_symptoms(user_input,all_symptoms)
    print("\nDetected symptoms:")
    for s in matched:
        print("-", process_sym(s))
    print("\nPossible diseases:")
    for disease, data in kb.items():
        if any(sym in data["symptoms"] for sym in matched):
            print(f"- {disease}")
            print("  Precautions:", ", ".join(data["precautions"]))


if __name__ == "__main__":
    main()