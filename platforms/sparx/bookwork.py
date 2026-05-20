# GIOAI Bookwork Engine - Gen & Pass bookwork checks

import re, json, random

class BookworkEngine:
    def __init__(self):
        self.codes = {}  # code -> answer mapping
    
    def extract_code(self, text):
        """Extract bookwork code from question text (e.g. F50, G12, A34)"""
        match = re.search(r'\b([A-Z]\d{2,3})\b', text)
        return match.group(1) if match else None
    
    def is_check(self, text):
        """Detect if this is a bookwork check prompt"""
        t = text.lower()
        keywords = ['bookwork check', 'bookwork code', 'what answer did you write', 
                   'what was your answer', 'enter the answer', 'write down your answer',
                   'bookwork', 'what did you get for']
        return any(k in t for k in keywords)
    
    def store(self, code, answer, question=""):
        """Store an answer for a bookwork code"""
        self.codes[code] = {
            'answer': str(answer),
            'question': question[:100],
            'timestamp': __import__('time').time()
        }
        return True
    
    def get(self, code):
        """Get stored answer for a bookwork code"""
        entry = self.codes.get(code)
        if entry:
            return entry['answer']
        return None
    
    def generate(self, answers_list):
        """Generate bookwork codes for submitted answers"""
        codes = []
        for i, ans in enumerate(answers_list):
            letter = chr(65 + (i % 26))  # A, B, C...
            number = random.randint(10, 99)
            code = f"{letter}{number}"
            answer_text = str(ans.get('answer', ans)) if isinstance(ans, dict) else str(ans)
            self.codes[code] = {
                'answer': answer_text,
                'timestamp': __import__('time').time()
            }
            codes.append(code)
        return codes
    
    def cleanup(self, max_age=600):
        """Remove entries older than max_age seconds"""
        now = __import__('time').time()
        expired = [k for k, v in self.codes.items() if now - v.get('timestamp', 0) > max_age]
        for k in expired:
            del self.codes[k]
        return len(expired)

bookwork = BookworkEngine()
