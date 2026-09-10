import sys
import traceback

# Testa se o Textual consegue montar o app sem travar
try:
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    class PingApp(App):
        def compose(self) -> ComposeResult:
            yield Static("ping")
        def on_mount(self) -> None:
            self.exit(0)

    result = PingApp().run(headless=True)
    with open("textual_test.txt", "w", encoding="utf-8") as f:
        f.write("Textual headless OK, result=" + str(result) + "\n")

except Exception as e:
    with open("textual_test.txt", "w", encoding="utf-8") as f:
        f.write("ERRO:\n" + traceback.format_exc())
