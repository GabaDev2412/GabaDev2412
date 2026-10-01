"""Render profile activity from GitHub's contribution data, without extra packages."""

import argparse
import json
import os
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate }
        contributions { totalCount }
      }
    }
  }
}
"""


def fetch_activity(login):
    token = os.environ["GH_TOKEN"]
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json", "User-Agent": "profile-activity"},
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors") or not result.get("data", {}).get("user"):
        raise RuntimeError("GitHub could not return contribution data; keeping the existing card.")
    collection = result["data"]["user"]["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    days = {day["date"]: day["contributionCount"]
            for week in calendar["weeks"] for day in week["contributionDays"]}
    public_commits = sum(item["contributions"]["totalCount"]
                         for item in collection["commitContributionsByRepository"]
                         if not item["repository"]["isPrivate"])
    return calendar["totalContributions"], public_commits, days


def render_card(login, total, commits, days):
    today = datetime.now(ZoneInfo("America/Recife")).date()
    dates = [today - timedelta(days=89-i) for i in range(90)]
    counts = [days.get(day.isoformat(), 0) for day in dates]
    active = sum(count > 0 for count in counts[-30:])
    peak = max(5, max(counts))
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="340" viewBox="0 0 900 340" role="img" aria-labelledby="title description">
<title id="title">Atividade de {escape(login)} no GitHub</title>
<desc id="description">{commits} commits públicos e {total} contribuições nos últimos 12 meses. {active} dias ativos nos últimos 30 dias. Gráfico diário dos últimos 90 dias; escala de 0 a {peak} contribuições.</desc>
<style>
text {{font-family: 'Segoe UI', Ubuntu, Arial, sans-serif}}
.label {{fill:#a6b5c8;font-size:14px}}
.value {{fill:#eff3f8;font-size:34px;font-weight:600}}
.period {{fill:#a6b5c8;font-size:12px}}
.bar {{animation:appear .65s ease both}}
@keyframes appear {{from {{opacity:0}} to {{opacity:1}}}}
@media (prefers-reduced-motion:reduce) {{.bar {{animation:none}}}}
</style>
<rect width="900" height="340" rx="12" fill="#080e16"/>
<path d="M28 30h24" stroke="#97c5fa" stroke-width="2" stroke-linecap="round"/>
<text x="64" y="35" fill="#97c5fa" font-size="14" font-weight="600" letter-spacing="1.5">ATIVIDADE NO GITHUB</text>''']
    for x, label, value, period in (
        (28, "Commits públicos", commits, "Últimos 12 meses"),
        (325, "Contribuições", total, "Últimos 12 meses"),
        (622, "Dias ativos", active, "Últimos 30 dias"),
    ):
        svg.append(f'<text class="label" x="{x}" y="76">{label}</text>'
                   f'<text class="value" x="{x}" y="115">{value:,}</text>'
                   f'<text class="period" x="{x}" y="137">{period}</text>')
    svg.append('<path d="M28 160h844" stroke="#1d2d40"/>'
               '<text class="label" x="28" y="185">Contribuições diárias · últimos 90 dias</text>')
    left, width, baseline, chart_height = 52, 820, 272, 66
    for value in (0, peak):
        y = baseline - chart_height * value / peak
        svg.append(f'<path d="M{left} {y:.2f}h{width}" stroke="#1d2d40"/>'
                   f'<text x="28" y="{y+4:.2f}" class="period">{value}</text>')
    step = width / len(counts)
    for i, (day, count) in enumerate(zip(dates, counts)):
        height = max(2, chart_height * count / peak)
        x, y = left + i * step, baseline - height
        color = "#97c5fa" if count else "#25364a"
        svg.append(f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" width="{step-2:.2f}" height="{height:.2f}" rx="1.5" fill="{color}" style="animation-delay:{i*4}ms">'
                   f'<title>{day.strftime("%d/%m/%Y")}: {count} contribuições</title></rect>')
    for index, anchor in ((0, "start"), (44, "middle"), (89, "end")):
        x = left + index * step + (step - 2 if index == 89 else 0)
        svg.append(f'<text x="{x:.2f}" y="293" class="period" text-anchor="{anchor}">{dates[index].strftime("%d/%m")}</text>')
    svg.append(f'<text x="28" y="321" class="period">Fonte: GitHub · Atualizado em {today.strftime("%d/%m/%Y")}</text></svg>')
    return "\n".join(svg) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", default="GabaDev2412")
    parser.add_argument("--output", type=Path, default=Path("assets/github-activity.svg"))
    args = parser.parse_args()
    total, commits, days = fetch_activity(args.login)
    if not days:
        raise RuntimeError("Empty contribution calendar; keeping the existing card.")
    svg = render_card(args.login, total, commits, days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Updated activity card for {args.login}.")


if __name__ == "__main__":
    main()
