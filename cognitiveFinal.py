import collections.abc
collections.Mapping = collections.abc.Mapping
from experta import TEST, Fact, Rule, DefFacts, KnowledgeEngine, MATCH
import re
import pandas as pd
from textblob import TextBlob
from nltk.corpus import stopwords
import nltk


def load_knowledge_base(csv_path):
    df=pd.read_csv(csv_path)
    df["precautions"] = df["precautions"].fillna("Consult a doctor immediately")
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
    new_text=[]
    for word in text.split():
        if word in stopword:
            new_text.append('')
        else:
            new_text.append(word)
    x=new_text[:]
    new_text.clear()
    return " ".join(x)

def preprocess(text):   #Lowercase ,misspellings, remove stopwords and tokenise 
    text=text.lower()
    text=remove_stopwords(text)
   # text=str(TextBlob(text).correct())
    text=re.sub(r"[^a-z\s]", " ", text)
    return text.split()

def extract_symptoms(user_text, all_symptoms):
    words=preprocess(user_text)
    user_phrase=" ".join(words)
    matched= set()
    for sym in all_symptoms:
        readable=sym.replace("_", " ")
        parts=readable.split()
        if readable in user_phrase or set(parts).issubset(words):            
            matched.add(sym)
    return list(matched)

def process_sym(sym):
    s= sym.replace("_", " ").replace("  ", " ").title()
    return s

class SymptomFact(Fact):
    # contains the user's matched symptoms and the knowledge base

    pass

class DiagnosisFact(Fact):
    # stores scored results after diagnosis rule fires
    pass
class FollowupFact(Fact):
    # Tries to handle followup questions.
    pass
class DiagnosisEngine(KnowledgeEngine):
    @DefFacts()
    def _init(self):
        yield Fact(action="diagnose")

    confidence_level = 0.5
    @Rule(Fact(action="diagnose"),SymptomFact(matched=MATCH.matched, kb=MATCH.kb,denied=MATCH.denied))
    def diagnose(self, matched, kb,denied):
        scores = []  ## for the confidence level
        for disease, info in kb.items():
            disease_syms = info["symptoms"]
            if len(disease_syms) == 0:
                continue
        #look for the intersection between user symptoms (in matched) and symptoms of disease(disease_syms)
            common_symptoms=set(matched).intersection(disease_syms)
            if common_symptoms:
                confidance=len(common_symptoms)/len(disease_syms)
                scores.append({
                "disease": disease,
                "confidance": confidance,
                "all_symptoms": disease_syms,
                "matched":list(matched) })

        if not scores:
          print("\nNo matching diseases found. Please describe your symptoms in more detail.")
          return    
        scores.sort(key=lambda x: x["confidance"], reverse=True)
           
        if scores[0]['confidance' ] <= self.confidence_level:
            # follow up logic
            self.declare(FollowupFact(scores=scores, matched=matched, kb=kb, denied=denied))
            self.declare(Fact(action="followup"))
        elif scores[0]['confidance'] > self.confidence_level:
            self.declare(DiagnosisFact(scores=scores, matched=matched, kb=kb))
     
    ## If confidence level > 0.5
    # confidence = matched symptoms / total disease symptoms
    ## if score >= confidence_level => display
    ## if score < confidence_level => follow_up
    @Rule(Fact(action="followup"), FollowupFact(scores=MATCH.scores, matched=MATCH.matched, kb=MATCH.kb, denied=MATCH.denied))
    def handle_followup(self, scores, matched, kb, denied):
        symptom_count = {}
        matched =list(matched)
        denied = list(denied)
        for disease in scores:
            for symptom in kb[disease["disease"]]["symptoms"]:
                if symptom not in matched and symptom not in denied:# this is to avoid asking previously asked symptoms
                    symptom_count[symptom] = symptom_count.get(symptom, 0) + 1


        if symptom_count:
            min_count = min(symptom_count.values())
            rare_symptom = [s for s in symptom_count if symptom_count[s] == min_count]
            rare_symptom = rare_symptom[:5]
            
            if len(rare_symptom) > 1:
                print(f"Which of these symptoms do you have?\n" + "\n".join(f"  - {s.replace('_',' ')}" for s in rare_symptom))
                print("Enter the ones you have separated by commas, or 'none'")
                choice = [c.strip() for c in input().split(",")]
                #choice = extract_symptoms(choice, rare_symptom) <-- this is needs the implemnted func in preprocessing
                for c in choice:
                    if c in rare_symptom:
                        matched.append(c)
                        
                denied.extend([s for s in rare_symptom if s not in matched])
            else:
                print(f"Do you have {rare_symptom[0].replace('_', ' ')}? (yes/no)")
                if input().lower().strip() == "yes":
                   matched.append(rare_symptom[0])
                else:
                   denied.append(rare_symptom[0])

            

            self.declare(SymptomFact(matched=matched, kb=kb, denied=denied))   #go back to rescore the diseases
        else:
            print("No more symptoms to ask about.")
            self.declare(DiagnosisFact(scores=scores, matched=matched, kb=kb))




    @Rule(DiagnosisFact(scores=MATCH.scores, kb=MATCH.kb))
    def show_results(self, scores,  kb):
        top = scores[:3]

        print("\n" + "="*30)
        print("DIAGNOSIS REPORT")
        print("="*30)
        for res in top:
            print(f"Disease: {res['disease']} | Confidence: {res['confidance']*100:.1f}%")

        top_disease = top[0]['disease']
        recommendations = kb[top_disease]["precautions"]
        print(f"\nPrecautions for {top_disease}:")
        for i, p in enumerate(recommendations, 1):
            print(f"   {i}. {p}")

def main():
    csv_path= "Medical Diagnosis Expert System.csv"
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
    
    engine = DiagnosisEngine()
    engine.reset()  
    engine.declare(SymptomFact(matched=matched, kb=kb, denied=[]))
    engine.run()


if __name__ == "__main__":
    main()
