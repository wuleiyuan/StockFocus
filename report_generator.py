import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from fpdf import FPDF


class ReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'StockFocus Investment Report', ln=True, align='C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')


class PDFReportGenerator:
    FONT_PATHS = [
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/System/Library/Fonts/AppleSDGothicNeo.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/System/Library/Fonts/PingFang.ttc',
    ]
    
    @classmethod
    def _try_load_chinese_font(cls, pdf: FPDF) -> bool:
        for font_path in cls.FONT_PATHS:
            try:
                if os.path.exists(font_path):
                    pdf.add_font('Chinese', '', font_path, uni=True)
                    pdf.set_font('Chinese', size=12)
                    return True
            except Exception:
                continue
        return False
    
    @classmethod
    def generate_report(cls, df: pd.DataFrame, output_dir: str = ".") -> str:
        if df is None or df.empty:
            return ""
        
        try:
            pdf = ReportPDF()
            pdf.add_page()
            
            if not cls._try_load_chinese_font(pdf):
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, 'StockFocus Daily Report', ln=True, align='C')
                pdf.set_font("Arial", size=12)
            else:
                pdf.set_font("Chinese", size=16)
                pdf.cell(0, 10, 'StockFocus 投研日报', ln=True, align='C')
                pdf.set_font("Chinese", size=12)
            
            pdf.ln(5)
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pdf.cell(0, 8, f'Generated: {date_str}', ln=True)
            pdf.ln(5)
            
            pdf.set_font("Arial", size=11)
            pdf.cell(0, 10, f'Total Stocks: {len(df)}', ln=True)
            
            golden_pits = df[df.get('bias', 0) < -15]
            undervalued = df[(df.get('bias', 0) >= -15) & (df.get('bias', 0) < -5)]
            fair_value = df[(df.get('bias', 0) >= -5) & (df.get('bias', 0) <= 20)]
            overvalued = df[df.get('bias', 0) > 20]
            
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, 'Summary:', ln=True)
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 8, f'Golden Pit (Bias < -15%): {len(golden_pits)} stocks', ln=True)
            pdf.cell(0, 8, f'Undervalued (-15% ~ -5%): {len(undervalued)} stocks', ln=True)
            pdf.cell(0, 8, f'Fair Value (-5% ~ 20%): {len(fair_value)} stocks', ln=True)
            pdf.cell(0, 8, f'Overvalued (> 20%): {len(overvalued)} stocks', ln=True)
            
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, 'Golden Pit Stocks:', ln=True)
            pdf.set_font("Arial", size=9)
            
            if not golden_pits.empty:
                pdf.cell(30, 7, 'Code', 1)
                pdf.cell(40, 7, 'Name', 1)
                pdf.cell(25, 7, 'Price', 1)
                pdf.cell(25, 7, 'Fair Price', 1)
                pdf.cell(25, 7, 'Bias %', 1)
                pdf.cell(25, 7, 'ROE %', 1)
                pdf.ln()
                
                for _, row in golden_pits.iterrows():
                    pdf.cell(30, 6, str(row.get('symbol', '')), 1)
                    pdf.cell(40, 6, str(row.get('name', ''))[:18], 1)
                    pdf.cell(25, 6, f"{row.get('current_price', 0):.2f}", 1)
                    pdf.cell(25, 6, f"{row.get('fair_price', 0):.2f}", 1)
                    pdf.cell(25, 6, f"{row.get('bias', 0):.1f}%", 1)
                    pdf.cell(25, 6, f"{row.get('roe_5y', 0):.1f}%", 1)
                    pdf.ln()
            else:
                pdf.cell(0, 8, 'No stocks in Golden Pit zone.', ln=True)
            
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, 'Complete Stock List:', ln=True)
            pdf.set_font("Arial", size=8)
            
            pdf.cell(20, 5, 'Code', 1)
            pdf.cell(35, 5, 'Name', 1)
            pdf.cell(20, 5, 'Price', 1)
            pdf.cell(20, 5, 'Fair', 1)
            pdf.cell(20, 5, 'Bias%', 1)
            pdf.cell(20, 5, 'ROE%', 1)
            pdf.cell(20, 5, 'Industry', 1)
            pdf.ln()
            
            for _, row in df.iterrows():
                pdf.cell(20, 5, str(row.get('symbol', '')), 1)
                pdf.cell(35, 5, str(row.get('name', ''))[:16], 1)
                pdf.cell(20, 5, f"{row.get('current_price', 0):.1f}", 1)
                pdf.cell(20, 5, f"{row.get('fair_price', 0):.1f}", 1)
                pdf.cell(20, 5, f"{row.get('bias', 0):.1f}", 1)
                pdf.cell(20, 5, f"{row.get('roe_5y', 0):.1f}", 1)
                pdf.cell(20, 5, str(row.get('industry', ''))[:10], 1)
                pdf.ln()
            
            filename = os.path.join(
                output_dir,
                f"StockFocus_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            pdf.output(filename)
            return filename
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"PDF generation failed: {e}")
            return ""


def generate_quick_report(df: pd.DataFrame, title: str = "StockFocus Report") -> str:
    return PDFReportGenerator.generate_report(df)
