import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, os, time, json, shutil, tempfile, subprocess
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
shutil.copytree(f"{ROOT}/proj", f"{tmp}/p")
os.chdir(f"{tmp}/p")
os.environ["PYTHONPATH"] = os.pathsep.join([os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))] + [x for x in sys.path if x])
os.environ["AUTOCLICK_SEM_OCR"] = "1"
from autoclick.interface.app import App
from autoclick.interface.dados import Geral, carregar_geral, salvar_geral
from autoclick.interface import comandos as CM, regras_form as RF, dados as DA
ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1

print("1) Argumentos montados pela janela")
g = Geral(janela="Roblox", ancora="mapa_ref", repeticao="loop", auto_detect=False)
a = CM.gravar(g)
check("gravar", a[0] == "gravar" and "--ancora" in a and "--gerar-regras" in a and "--janela" in a and a[a.index("--janela") + 1] == "Roblox", str(a))
a = CM.reproduzir(g)
check("reproduzir em loop sem auto_detect", "--loop" in a and a[a.index("--loop") + 1].startswith("--") and "--sem-auto-detect" in a, str(a))
a = CM.reproduzir(Geral(repeticao="n", voltas=5, teclado=False, checar_janela=False))
check("reproduzir N vezes", a[a.index("--loop") + 1] == "5" and "--sem-teclado" in a and "--sem-checar-janela" in a and "--janela" not in a, str(a))
a = CM.reproduzir(Geral())
check("reproduzir uma vez: sem --loop", "--loop" not in a)
a = CM.automatico(Geral(modo_auto="texto", palavras="ok sim", variacao=0.15, inatividade=600, log="l.csv", relatorio="r.md"))
check("automático texto", a[0] == "texto" and a[a.index("--palavras") + 1:a.index("--palavras") + 3] == ["ok", "sim"] and "--variacao" in a and "--ao-travar" in a and "--relatorio" in a, str(a))
a = CM.automatico(Geral(), preview=True)
check("preview não leva relatório", "--preview" in a and "--relatorio" not in a and a[0] == "imagem")
check("texto de ajuda legível", CM.para_texto(["gravar", "--janela", "Meu Jogo"]).endswith('--janela "Meu Jogo"'))

print("2) Formulário de regra")
c = RF.regra_para_campos({"acao": "arrastar", "destino": {"ancora": "mapa_ref", "offset": [320, -140]}})
check("campos de destino por âncora", c["dest_tipo"] == "ancora" and c["dest_dx"] == "320" and c["vezes"] == "1")
r, e = RF.campos_para_regra({"acao": "arrastar", "destino": {"ancora": "mapa_ref", "offset": [320, -140]}, "extra": 7}, c)
check("ida e volta sem mudar nada", r == {"acao": "arrastar", "destino": {"ancora": "mapa_ref", "offset": [320, -140]}, "extra": 7} and not e, str((r, e)))
c["dest_tipo"] = "janela"; c["dest_fx"] = "0.62"; c["dest_fy"] = "0.55"; c["auto_detect"] = "sim"; c["queda"] = "0.4"; c["requer"] = "a, b"
r, e = RF.campos_para_regra({}, c)
check("destino por janela + extras", r["destino"] == {"janela": [0.62, 0.55]} and r["auto_detect"] is True and r["queda_saturacao"] == 0.4 and r["requer"] == ["a", "b"] and not e, str((r, e)))
c["dest_tipo"] = "nenhum"
_, e = RF.campos_para_regra({}, c)
check("arrastar sem destino dá erro claro", any("destino" in x for x in e))
c2 = RF.regra_para_campos({}); c2["vezes"] = "abc"
_, e = RF.campos_para_regra({}, c2)
check("número inválido dá erro", any("vezes" in x for x in e))
c2 = RF.regra_para_campos({"acao": "clicar"}); c2["escolha"] = "primeiro"; c2["grupo"] = "cartas"; c2["reiniciar_loop"] = "1"
r, e = RF.campos_para_regra({}, c2)
check("escolha + grupo + reiniciar_loop", r == {"acao": "clicar", "escolha": "primeiro", "grupo": "cartas", "reiniciar_loop": True}, str(r))
et, e = RF.campos_para_etapa({"etapa": "lobby", "quando": "jogar, x", "timeout": "300", "ao_estourar": "parar"})
check("etapa", et == {"etapa": "lobby", "quando": ["jogar", "x"], "timeout": 300.0, "ao_estourar": "parar"} and not e, str(et))

print("3) Janela (Tk)")
g = Geral(tema="escuro")
app = App(g, os.getcwd())
r = app.raiz
def bombear(seg=0.0, ate=None, limite=15.0):
    t0 = time.time()
    while True:
        r.update()
        if ate is not None and ate(): return True
        if time.time() - t0 > (limite if ate else seg): return ate is None
        time.sleep(0.02)
check("7 páginas + Jogos dentro de Configurações", set(app.paginas) == {"gravar", "rotinas", "auto", "regras", "historico", "config", "ajuda"} and set(app.subpaginas) == {"jogos"})
app.raiz.update(); check("página inicial = Gravar", app.g.pagina == "gravar" and app.paginas["gravar"].frame.winfo_ismapped())
check("resumo da gravação exibido", "3 eventos" in app.paginas["gravar"].info.cget("text"), app.paginas["gravar"].info.cget("text"))
pg = app.paginas["gravar"]
pg.v_rep.set("n"); r.update()
check("campo de voltas habilita em 'repetir N vezes'", "disabled" not in pg.sp_voltas.state())
pg.v_rep.set("loop"); r.update()
check("…e desabilita em loop", "disabled" in pg.sp_voltas.state())
check("variáveis gravam nas configurações", app.g.repeticao == "loop")
app.var("velocidade")
pg.esc_vel.set(2.0); r.update()
check("slider de velocidade grava 2.0", app.g.velocidade == 2.0)

print("4) Processo de verdade (validar)")
app.log_texto("", "")
r.update()
acabou = []
app.ir("regras")
app.rodar("ferramenta", CM.validar(app.g), ao_fim=lambda c: acabou.append(c))
check("chip mostra execução", app.chip.cget("text") != "Parado" or acabou)
bombear(ate=lambda: bool(acabou))
txt = app.log.get("1.0", "end")
check("saída do processo aparece no console", "validar" in txt and ("fantasma" in txt or "erro" in txt.lower()), txt[-400:])
check("voltou ao estado Parado", app.chip.cget("text") == "Parado" and not app.rodando)
check("código de saída reportado", acabou and acabou[0] in (0, 1), str(acabou))
app.ir("config"); r.update()
check("página de configurações lista dependências", len(app.paginas["config"].quadro_deps.winfo_children()) == 5)

print("5) Protocolo de controle (pausa / status / parar)")
app.exec.comando_base = [sys.executable, "-u", f"{ROOT}/fake_proc.py"]
fim = []
app.paginas["gravar"].frame  # existe
app.ir("auto")
acabou.clear()
assert app.rodar("imagem", [], ao_fim=lambda c: fim.append(c))
bombear(ate=lambda: app._ultimo_status.get("resumo", {}).get("total_acoes", 0) >= 3)
check("status chega com contadores", app._ultimo_status["resumo"]["cliques"].get("botao_x", 0) >= 3)
check("painel mostra ações", app.paginas["auto"].painel.blocos["acoes"].valor.cget("text") != "0")
check("chip: Automático", app.chip.cget("text") == "Automático")
app.alternar_pausa()
bombear(ate=lambda: app.exec.pausado)
check("pausa recebida (chip Pausado)", bombear(ate=lambda: app.chip.cget("text") == "Pausado"))
n1 = app._ultimo_status["resumo"]["total_acoes"]; bombear(1.0)
n2 = app._ultimo_status["resumo"]["total_acoes"]
check("pausado: contagem não avança", n2 - n1 <= 1, f"{n1}->{n2}")
check("botão vira Continuar", app.btn_pausa.cget("text") == "Continuar")
app.alternar_pausa()
bombear(ate=lambda: app._ultimo_status["resumo"]["total_acoes"] > n2 + 2)
check("continua depois da pausa", app._ultimo_status["resumo"]["total_acoes"] > n2 + 2)
app.parar()
check("parar encerra o processo sozinho", bombear(ate=lambda: bool(fim) and not app.rodando))
check("saída limpa do processo", "fake parou limpo" in app.log.get("1.0", "end"))

print("6) Editor de regras")
rg = app.paginas["regras"]
app.ir("regras"); r.update()
check("lista mostra PNGs e regras", set(rg.arvore.get_children()) >= {"torre", "maximo", "fantasma", "mapa_ref", "jogar_novamente"})
check("regra sem imagem marcada", "falta" in rg.arvore.item("fantasma", "tags"))
rg.arvore.selection_set("maximo"); r.update()
check("formulário carrega a regra", rg.v["auto_detect"].get() == "sim" and rg.lbl_nome.cget("text") == "maximo")
check("miniatura carregada", rg._thumb is not None)
rg.v["intervalo"].set("2"); rg.v["vezes"].set("3"); rg.salvar(); r.update()
d = json.load(open("botoes.json"))
check("regra salva no json (e o resto preservado)", d["maximo"] == {"acao": "clicar", "auto_detect": True, "vezes": 3, "intervalo": 2.0} and d["_janela"] == "Roblox" and "_fluxo" in d, str(d["maximo"]))
rg.arvore.selection_set("torre"); r.update()
check("seção de arrastar visível só para arrastar", rg.s4.winfo_manager() == "pack")
rg.v["acao"].set("clicar"); rg._visibilidade(); r.update()
check("…e some para clicar", rg.s4.winfo_manager() == "")
rg.v["acao"].set("arrastar"); rg._visibilidade()
rg.v["dest_tipo"].set("nenhum")
import tkinter.messagebox as mb
avisos = []; mb.showwarning = lambda *a, **k: avisos.append(a)
import autoclick.interface.pag_regras as PR
PR.messagebox.showwarning = lambda *a, **k: avisos.append(a)
check("arrastar sem destino: não salva, avisa", rg.salvar() is False and avisos)
rg.v["dest_tipo"].set("janela"); rg.v["dest_fx"].set("0.5"); rg.v["dest_fy"].set("0.25"); rg._visibilidade()
check("salva destino por janela", rg.salvar() and json.load(open("botoes.json"))["torre"]["destino"] == {"janela": [0.5, 0.25]})
rg.arvore.selection_set("mapa_ref"); r.update()
check("âncora não mostra seções de clique", rg.s2.winfo_manager() == "")
# nova imagem sem regra
shutil.copy("botoes/maximo.png", "botoes/nova.png"); rg.recarregar(); r.update()
check("PNG sem regra listado", "sem_regra" in rg.arvore.item("nova", "tags"))
rg.arvore.selection_set("nova"); r.update(); rg.v["escolha"].set("primeiro"); rg.salvar()
check("criar regra para PNG novo", json.load(open("botoes.json"))["nova"] == {"acao": "clicar", "escolha": "primeiro"})
rg.remover = rg.remover
PR.messagebox.askyesno = lambda *a, **k: True
rg.arvore.selection_set("nova"); rg.remover()
check("remover regra", "nova" not in json.load(open("botoes.json")))
# fluxo
dlg = PR.DialogoFluxo(rg)
check("fluxo carrega etapas existentes", len(dlg.etapas) == 1 and dlg.etapas[0]["etapa"] == "lobby")
dlg.v["etapa"].set("partida"); dlg.v["quando"].set("maximo"); dlg.v["timeout"].set("1800"); dlg.v["ao_estourar"].set("parar"); dlg.adicionar()
dlg.salvar(); r.update()
f = json.load(open("botoes.json"))["_fluxo"]
check("etapa nova salva", [e["etapa"] for e in f] == ["lobby", "partida"] and f[1]["ao_estourar"] == "parar", str(f))
check("combo de etapas atualizado", "partida" in rg.cb_etapa.cget("values"))

print("7) Automático e opcionais (sem Tesseract)")
au = app.paginas["auto"]
check("OCR ausente detectado", au.ocr_ok is False)
check("modo escolhido volta para imagem", app.g.modo_auto == "imagem")
app.g.modo_auto = "texto"
shown = []
import autoclick.interface.pag_auto as PA
PA.messagebox.showinfo = lambda *a, **k: shown.append(a)
check("iniciar em modo OCR sem OCR: avisa e não roda", au._validar() is False and shown and not app.rodando)
app.g.modo_auto = "imagem"
check("modo imagem libera", au._validar() is True)

print("8) CLI sem dependências opcionais")
r1 = subprocess.run([sys.executable, "-m", "autoclick", "texto", "--preview"], capture_output=True, text=True, timeout=60)
check("modo texto sem OCR: mensagem amigável (sem Traceback)", "Traceback" not in r1.stderr and "OCR" in (r1.stdout + r1.stderr) and r1.returncode != 0, r1.stderr[-300:])
r2 = subprocess.run([sys.executable, "-m", "autoclick", "validar"], capture_output=True, text=True, timeout=60)
check("validar roda sem mss/OCR", "Traceback" not in r2.stderr and "erro(s)" in r2.stdout + r2.stderr or "problema" in r2.stdout, r2.stderr[-300:] + r2.stdout[-200:])

print("9) Perfis e tema")
cf = app.paginas["config"]
import autoclick.interface.pag_config as PC
PC.pedir_texto = lambda *a, **k: "meujogo"
app.g.janela = "Roblox"
cf.salvar_perfil()
p = json.load(open("perfis/meujogo.json"))
check("perfil salvo com opções do terminal", p["modo"] == "imagem" and p["janela"] == "Roblox" and p["pasta"] == "botoes", str(p))
app.g.janela = "outra"; app.g.intervalo = 9.0
cf.v_perfil.set("meujogo"); cf.carregar_perfil(); r.update()
check("perfil carregado de volta", app.g.janela == "Roblox")
app.trocar_tema("claro"); r.update()
check("tema claro recria a janela", app.t.nome == "claro" and len(app.paginas) == 7)
salvar_geral(app.g)
check("configurações persistem", carregar_geral().tema == "claro" and carregar_geral().janela == "Roblox")

print("10) Entrada do programa")
import autoclick.inicio as IN, autoclick.interface as IFC
chamadas = []
IFC.abrir_app = lambda: chamadas.append("gui")
sys.argv = ["autoclick"]; IN.principal()
check("sem argumentos abre a janela", chamadas == ["gui"])
app.raiz.destroy()
print(f"\n{ok} verificações passaram (GUI).")
