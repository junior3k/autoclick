"use strict";
(function () {
  var base = location.pathname.replace(/\/painel\/?$/, "");
  var token = "";
  try { token = sessionStorage.getItem("ac_token") || ""; } catch (e) {}
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, props, filhos) {
    var e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === "texto") e.textContent = props[k]; else if (k === "onclick") e.onclick = props[k]; else e.setAttribute(k, props[k]);
    });
    (filhos || []).forEach(function (f) { e.appendChild(f); });
    return e;
  }
  function aviso(texto, ruim) { var m = $("msg"); m.textContent = texto; m.className = ruim ? "erro" : "ok"; }

  function api(metodo, caminho, corpo) {
    return fetch(base + "/admin" + caminho, {
      method: metodo,
      headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
      cache: "no-store"
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (r.status === 401) { sair(); throw new Error("sessão expirada"); }
        if (!r.ok) throw new Error(d.erro || ("HTTP " + r.status));
        return d;
      });
    });
  }
  function acao(metodo, caminho, corpo, ok, depois) {
    return api(metodo, caminho, corpo).then(function (d) { aviso(ok || "Feito.", false); if (depois) depois(d); }, function (e) { aviso(e.message, true); });
  }

  function tabela(id, colunas, linhas, acoes) {
    var t = $(id); t.textContent = "";
    var tr = el("tr", {}, colunas.map(function (c) { return el("th", { texto: c[1] }); }));
    if (acoes) tr.appendChild(el("th", { texto: "Ações" }));
    t.appendChild(el("thead", {}, [tr]));
    var corpo = el("tbody");
    linhas.forEach(function (l) {
      var r = el("tr", {}, colunas.map(function (c) {
        var v = l[c[0]]; if (c[2]) v = c[2](v, l);
        return el("td", { texto: v === null || v === undefined ? "" : String(v) });
      }));
      if (acoes) r.appendChild(el("td", {}, [el("div", { "class": "acoes" }, acoes(l))]));
      corpo.appendChild(r);
    });
    if (!linhas.length) corpo.appendChild(el("tr", {}, [el("td", { texto: "(vazio)" })]));
    t.appendChild(corpo);
  }
  function botao(texto, fn, cls) { return el("button", { texto: texto, onclick: fn, "class": cls || "sec", type: "button" }); }
  function dt(v) { return v ? v.replace("T", " ").replace(/\+00:00$/, " UTC") : ""; }

  function resumo() {
    api("GET", "/status").then(function (s) {
      var itens = [["Instalações", s.instalacoes], ["Ativas 24h", s.instalacoes_ativas_24h],
        ["Estável", s.ultima_estavel || "—"], ["Beta", s.ultima_beta || "—"], ["No site", s.download || "—"], ["Pacotes (MB)", s.pacotes_mb],
        ["Relatórios", s.relatorios], ["Backups", s.backups]];
      var c = $("cartoes"); c.textContent = "";
      itens.forEach(function (i) { c.appendChild(el("div", { "class": "cartao" }, [el("b", { texto: String(i[1]) }), el("span", { texto: i[0] })])); });
      $("aviso").value = s.aviso || "";
      var l = $("link-pagina"); l.textContent = s.pagina; l.href = s.pagina;
      var pv = Object.keys(s.ativas_por_versao || {}).map(function (k) { return k + ": " + s.ativas_por_versao[k]; });
      $("por-versao").textContent = pv.length ? "Ativas por versão — " + pv.join(" · ") : "";
    }, function (e) { aviso(e.message, true); });
  }
  function versoes() {
    api("GET", "/versoes").then(function (l) {
      tabela("t-versoes", [["versao", "Versão"], ["artefato", "Pacote"], ["canal", "Canal"], ["percentual", "%"], ["minima", "Mínima"],
        ["tamanho", "MB", function (v) { return (v / 1048576).toFixed(1); }], ["publicada", "Publicada", dt]], l, function (v) {
        var r = [];
        if (v.canal === "beta") r.push(botao("Promover", function () { acao("POST", "/versoes/" + v.versao + "/promover", { canal: "estavel" }, "Promovida.", versoes); }));
        if (v.canal === "estavel") r.push(botao("Voltar p/ beta", function () { acao("POST", "/versoes/" + v.versao + "/promover", { canal: "beta" }, "Movida.", versoes); }));
        if (v.canal !== "retirada") r.push(botao("Retirar", function () { if (confirm("Retirar " + v.versao + "?")) acao("POST", "/versoes/" + v.versao + "/retirar", {}, "Retirada.", versoes); }, "perigo"));
        r.push(botao("%", function () { var x = prompt("Liberar para quantos % das instalações? (1-100)", v.percentual); if (x) acao("POST", "/versoes/" + v.versao + "/percentual", { valor: parseInt(x, 10) }, "Atualizado.", versoes); }));
        r.push(botao("Mínima", function () { var x = prompt("Versão mínima obrigatória (0 = nenhuma)", v.minima); if (x) acao("POST", "/versoes/" + v.versao + "/minima", { minima: x }, "Atualizado.", versoes); }));
        return r;
      });
    }, function (e) { aviso(e.message, true); });
  }
  function relatorios() {
    api("GET", "/relatorios").then(function (l) {
      tabela("t-relatorios", [["criado", "Data", dt], ["instalacao", "Instalação"], ["resumo", "Resumo"], ["tamanho", "KB", function (v) { return Math.round(v / 1024); }]], l, function (r) {
        return [botao("Baixar", function () {
          fetch(base + "/admin/relatorios/" + r.id, { headers: { "Authorization": "Bearer " + token } }).then(function (x) { return x.blob(); }).then(function (b) {
            var a = el("a", { href: URL.createObjectURL(b), download: "relatorio_" + r.id + ".zip" }); document.body.appendChild(a); a.click(); a.remove();
          });
        }), botao("Apagar", function () { if (confirm("Apagar?")) acao("POST", "/relatorios/" + r.id + "/apagar", {}, "Apagado.", relatorios); }, "perigo")];
      });
    }, function (e) { aviso(e.message, true); });
  }
  function eventos() {
    api("GET", "/eventos").then(function (l) {
      tabela("t-eventos", [["t", "Quando", dt], ["tipo", "Tipo"], ["amigo", "Quem"], ["detalhe", "Detalhe"]], l);
    }, function (e) { aviso(e.message, true); });
  }

  var abas = { "Resumo": resumo, "Versões": versoes, "Relatórios": relatorios, "Eventos": eventos };
  function abrir(nome) {
    Array.prototype.forEach.call(document.querySelectorAll("section"), function (s) { s.className = s.getAttribute("data-aba") === nome ? "on" : ""; });
    Array.prototype.forEach.call($("abas").children, function (b) { b.className = b.textContent === nome ? "on" : ""; });
    $("msg").textContent = ""; abas[nome]();
  }
  function entrar() {
    $("entrada").hidden = true; $("app").hidden = false; $("sair").hidden = false;
    var n = $("abas"); n.textContent = "";
    Object.keys(abas).forEach(function (k) { n.appendChild(botao(k, function () { abrir(k); })); });
    abrir("Resumo");
  }
  function sair() {
    token = ""; try { sessionStorage.removeItem("ac_token"); } catch (e) {}
    $("app").hidden = true; $("sair").hidden = true; $("entrada").hidden = false; $("token").value = "";
  }

  $("sair").onclick = sair;
  $("form-token").onsubmit = function (ev) {
    ev.preventDefault(); token = $("token").value.trim();
    api("GET", "/status").then(function () { try { sessionStorage.setItem("ac_token", token); } catch (e) {} $("erro-token").textContent = ""; entrar(); },
      function () { token = ""; $("erro-token").textContent = "Token inválido."; });
  };
  $("form-aviso").onsubmit = function (ev) { ev.preventDefault(); acao("POST", "/aviso", { texto: $("aviso").value }, "Aviso salvo."); };
  $("bt-backup").onclick = function () { acao("POST", "/backup", {}, "Backup feito.", function (d) { $("backups").textContent = d.arquivo; resumo(); }); };

  if (token) api("GET", "/status").then(entrar, function () {});
})();
