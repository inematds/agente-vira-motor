import io, json, pathlib, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout
AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from motor import fontes  # noqa
import alerta, semana  # noqa
FIX = AQUI / "fixtures"


class Fontes(unittest.TestCase):
    def test_le_os_quatro_tipos(self):
        regs = fontes.ler_tudo(FIX)
        tipos = {r.tipo for r in regs}
        self.assertEqual(tipos, {"falha", "limite", "revisor", "licao"})
        rev = [r for r in regs if r.tipo == "revisor"]
        self.assertEqual(rev[0].nota, 5.0)
        self.assertTrue(rev[1].dono)
        self.assertEqual(rev[0].texto, "começa pelo inventário, sem dor")
        self.assertEqual(len([r for r in regs if r.tipo == "licao"]), 1)   # lição sem data fica de fora

    def test_causa_e_status(self):
        regs = fontes.ler_tudo(FIX)
        self.assertIn("infra", [r.causa for r in regs if r.tipo == "falha"])
        self.assertEqual([r.status for r in regs if r.tipo == "limite"], ["aberto", "aceito"])

    def test_duplicata_conta_uma_vez(self):
        with tempfile.TemporaryDirectory() as d:
            for p in ("a", "a-publico"):
                (pathlib.Path(d) / p).mkdir()
                (pathlib.Path(d) / p / "FALHAS.md").write_text("| 2026-11-20 | igual | x | infra |\n")
            self.assertEqual(len(fontes.ler_tudo(pathlib.Path(d))), 1)

    def test_pasta_sem_permissao_nao_quebra(self):
        with tempfile.TemporaryDirectory() as d:
            trancada = pathlib.Path(d) / "db"
            trancada.mkdir()
            trancada.chmod(0)
            try:
                fontes.ler_tudo(pathlib.Path(d))
            finally:
                trancada.chmod(0o755)


class Alerta(unittest.TestCase):
    def rodar(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cod = alerta.main(["--raiz", str(FIX), "--hoje", "2026-11-20", *args])
        return cod, buf.getvalue()

    def test_acha_o_erro_que_voltou(self):
        cod, txt = self.rodar()
        self.assertEqual(cod, 1)
        self.assertIn("identify ausente", txt)
        self.assertIn("2× antes", txt)          # outubro e início de novembro
        self.assertIn("extensão desconectada", txt)

    def test_curto_cabe_no_celular(self):
        _, txt = self.rodar("--curto")
        self.assertLess(len(txt), 700)
        self.assertIn("VOLTOU A ACONTECER", txt)

    def test_dia_sem_nada(self):
        cod, txt = self.rodar("--hoje", "2026-12-25", "--curto")
        self.assertEqual(cod, 0)
        self.assertIn("Nada pede ação", txt)


class Semana(unittest.TestCase):
    def test_reincidencia_e_degrau(self):
        regs = fontes.ler_tudo(FIX)
        import datetime as dt
        s = semana.resumo(regs, dt.date(2026, 11, 20), 0.34)
        self.assertGreater(s["reincidencia"], 0)
        temas = {t["assunto"]: t for t in s["temas"]}
        self.assertTrue(any("identify" in a for a in temas))
        self.assertEqual(semana.degrau(9)[0], "motor")
        self.assertEqual(semana.degrau(4)[0], "trava")
        self.assertEqual(semana.degrau(2)[0], "teste")

    def test_grava_foto_e_compara(self):
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()):
                semana.main(["--raiz", str(FIX), "--hoje", "2026-11-13", "--pasta", d])
                semana.main(["--raiz", str(FIX), "--hoje", "2026-11-20", "--pasta", d])
            self.assertTrue((pathlib.Path(d) / "2026-11-20.json").is_file())
            self.assertIn("Reincidência", (pathlib.Path(d) / "2026-11-20.md").read_text())


class Medir(unittest.TestCase):
    def test_checador_oculto(self):
        import medir
        t = AQUI.parent / "tarefas" / "classificar-falhas"
        gab = json.loads((t / "oculto" / "gabarito.json").read_text())
        self.assertEqual(medir.checar(t, json.dumps(gab))["nota"], 10.0)
        self.assertEqual(medir.checar(t, "não sei")["nota"], 0.0)
        self.assertEqual(medir.checar(t, "```json\n" + json.dumps(gab) + "\n```")["nota"], 10.0)

    def test_simulado_sem_modelo(self):
        with tempfile.TemporaryDirectory() as d:
            cp = subprocess.run([sys.executable, str(AQUI.parent / "medir.py"), str(AQUI.parent / "tarefas/classificar-falhas"),
                                 "--simular", "--modelos", "a,b", "--esforcos", "low,high", "--saida", d],
                                capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertEqual(len((pathlib.Path(d) / "rodadas.jsonl").read_text().splitlines()), 4)

    def test_sem_chave_de_api(self):
        import os, medir
        os.environ["ANTHROPIC_API_KEY"] = "x"
        try:
            self.assertNotIn("ANTHROPIC_API_KEY", medir.env_assinatura())
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


if __name__ == "__main__":
    unittest.main()
