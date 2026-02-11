from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", 'B', 16)
pdf.cell(40, 10, 'StockFocus Web Pro User Manual')
pdf.ln(10)
pdf.set_font("Arial", size=12)
pdf.multi_cell(0, 10, "1. 15x PE Strategy: Valuation anchor.\n2. AI Search: Natural language query.\n3. AI Assistant: Research report summary.\n4. Poster: One-click generation for sharing.")
pdf.output("StockFocus_User_Manual.pdf")
print("✅ 说明书已生成！")