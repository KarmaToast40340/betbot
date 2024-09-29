import main


with open("matches.json", "w", encoding="utf-8") as file:
  data = parions_sport.get_html()
  file.write(data)

with open("matches2.json", "w", encoding="utf-8") as file:
  data = parions_sport.get_html()
  file.write(data)

