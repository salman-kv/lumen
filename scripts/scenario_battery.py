"""Broad scenario check (44 questions: boundaries, paraphrases, typos, caps, off-topic, cross-tenant, long input).
Run after seed_and_eval.py: cd backend && uv run python ../scripts/scenario_battery.py"""
import httpx,json,sys,time
c=httpx.Client(base_url="http://localhost:8000",timeout=300)
tok=json.load(open(__import__("pathlib").Path(__file__).resolve().parents[1] / "sample_data" / ".tokens.json"))
N,A=tok["northfield"],tok["acme"]
# (org, question, expected status, expected verdict or None, note)
T=[
(N,"I have a 3.5 GPA, I'm in my second year and don't hold a sports scholarship. Merit scholarship?","answered","eligible","boundary exact"),
(N,"I'm a 2nd year student, GPA 3.49, no sports scholarship, am I eligible for merit scholarship","answered","not_eligible","boundary just below"),
(N,"Am I eligible for the merit scholarship? I'm a sophomore with a 3.7 GPA and I don't have any sports scholarship","answered","eligible","sophomore"),
(N,"merit scholarship eligible? year 3, gpa 3.9, currently holding sports scholarship","answered","not_eligible","holding"),
(N,"I am in year one with gpa 3.9 and no sports scholarship, can I get merit scholarship?","answered","not_eligible","year one"),
(N,"Can a fourth-year student with GPA 3.6 who has no sports scholarship get the merit scholarship?","answered","eligible","fourth-year"),
(N,"Do I qualify for the sports scholarship? GPA 3.0, attendance 85%, and I have a coach recommendation letter","answered","eligible","sports ok"),
(N,"Do I qualify for the sports scholarship? GPA 2.5, attendance 85%, I have a coach recommendation letter","answered","not_eligible","sports gpa low"),
(N,"Am I eligible for sports scholarship with 70% attendance, GPA 3.2 and a coach recommendation?","answered","not_eligible","sports attendance"),
(N,"Can I get the fee waiver? My GPA is 3.2 and I have a hardship letter","answered","eligible","fee waiver"),
(N,"Am I eligible for the fee waiver with a 2.5 GPA and a hardship letter?","answered","not_eligible","fee waiver low"),
(N,"Am I eligible for the fee waiver?","needs_info","need_info","fee waiver no facts"),
(N,"What GPA do I need for the merit scholarship?","answered",None,"direct about threshold, not decision"),
(N,"What are the requirements for the sports scholarship?","answered",None,"requirements"),
(N,"What documents do I need to apply for admission?","answered",None,"documents"),
(N,"how much is the tution fee for international studnts","answered",None,"typos"),
(N,"WHAT IS THE REFUND POLICY???","answered",None,"caps"),
(N,"Tell me about the scholarships you offer","answered",None,"overview"),
(N,"Summarize the fee policy","answered",None,"summarize"),
(N,"When is the deadline to apply and what documents are required?","answered",None,"multi-part"),
(N,"Who do I contact about financial aid?","any",None,"maybe none"),
(N,"What is the capital of France?","no_knowledge",None,"offtopic"),
(N,"How do I cook pasta?","no_knowledge",None,"offtopic"),
(N,"Can I get a refund for my laptop purchase?","no_knowledge",None,"offtopic refund trap"),
(N,"What is the leave policy for employees?","no_knowledge",None,"cross-tenant"),
(N,"x"*3000,"any",None,"very long input"),
(N,"What is the scholarship appeal process? 🎓","answered",None,"emoji"),
(A,"I've been here 7 months, have an approved remote work agreement, can I work remotely 3 days per week?","answered","eligible","remote ok"),
(A,"I've been here 7 months, have an approved remote work agreement, can I work remotely 4 days a week?","answered","not_eligible","remote 4 days"),
(A,"I have 4 months of service and an approved remote work agreement. Can I work remotely 2 days per week?","answered","not_eligible","remote tenure"),
(A,"I have 10 months of service. Can I work remotely 2 days per week? I don't have an approved remote work agreement","answered","not_eligible","remote no agreement"),
(A,"Am I eligible for parental leave? I've worked here 12 months","answered","eligible","parental boundary"),
(A,"I've worked here for 2 years. Can I take parental leave?","answered","eligible","2 years"),
(A,"Am I eligible for the home office allowance? I've worked for 4 months","answered","eligible","home office"),
(A,"Can I get the home office allowance after 2 months?","answered","not_eligible","home office low"),
(A,"Can I take annual leave? I have manager approval and will request 20 days in advance","answered","eligible","annual leave"),
(A,"Can I take annual leave next week with manager approval? I'm asking 3 days in advance","answered","not_eligible","annual leave short"),
(A,"Who approves a $900 expense?","answered",None,"expense amount"),
(A,"What is the approval process for expenses over $5000?","answered",None,"expense big"),
(A,"How many days of annual leave do I get and can I carry them over?","answered",None,"multi-part"),
(A,"What is the difference between annual leave and parental leave?","answered",None,"comparison"),
(A,"How do I submit an expense report?","any",None,"procedural"),
(A,"What is the GPA for scholarships?","no_knowledge",None,"cross-tenant"),
(A,"I'm a student with 3.9 GPA, can I get the merit scholarship?","no_knowledge",None,"cross-tenant decision"),
]
bad=0
for org,q,st,vd,note in T:
    t=time.time()
    try:
        r=c.post("/api/ask",json={"token":org,"question":q}).json()
    except Exception as e:
        print("ERR",note,e); bad+=1; continue
    s=r.get("status"); v=(r.get("decisions") or {}).get("verdict")
    ok=(st=="any" or s==st) and (vd is None or v==vd)
    if not ok: bad+=1
    print(("OK  " if ok else "FAIL"),f"{time.time()-t:4.1f}s",note,"|",s,v,"|",(r.get("answer") or r.get("detail") or "")[:130].replace("\n"," "))
print("bad",bad,"of",len(T))
