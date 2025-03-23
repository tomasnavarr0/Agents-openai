import time
import base64
from playwright.sync_api import sync_playwright
from openai import OpenAI  # Se asume que existe un cliente OpenAI compatible con CUA

def handle_model_action(page, action):
    """
    Ejecuta la acción sugerida por el modelo en la página.
    Se utilizan las construcciones match-case (requiere Python 3.10+).
    """
    action_type = action.get("type")
    try:
        match action_type:
            case "click":
                x, y = action.get("x"), action.get("y")
                button = action.get("button", "left")
                print(f"Acción: click en ({x}, {y}) con botón '{button}'")
                # Por seguridad se comprueba el botón
                if button not in ["left", "right"]:
                    button = "left"
                page.mouse.click(x, y, button=button)
            case "scroll":
                # Se extraen las coordenadas y offsets del scroll
                x, y = action.get("x"), action.get("y")
                scroll_x, scroll_y = action.get("scroll_x", 0), action.get("scroll_y", 0)
                print(f"Acción: scroll en ({x}, {y}) con offset (x={scroll_x}, y={scroll_y})")
                page.mouse.move(x, y)
                page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
            case "keypress":
                keys = action.get("keys", [])
                for k in keys:
                    print(f"Acción: pulsación de tecla '{k}'")
                    if k.lower() == "enter":
                        page.keyboard.press("Enter")
                    elif k.lower() == "space":
                        page.keyboard.press(" ")
                    else:
                        page.keyboard.press(k)
            case "type":
                text = action.get("text", "")
                print(f"Acción: escribir texto: {text}")
                page.keyboard.type(text)
            case "wait":
                print("Acción: espera de 2 segundos")
                time.sleep(2)
            case "screenshot":
                print("Acción: capturar screenshot (se hace automáticamente)")
            case _:
                print(f"Acción no reconocida: {action}")
    except Exception as e:
        print(f"Error al ejecutar la acción {action}: {e}")

def get_screenshot(page):
    """
    Toma un screenshot completo de la página y devuelve los bytes de la imagen.
    """
    return page.screenshot()

def computer_use_loop(page, client, response):
    """
    Ejecuta en bucle las acciones sugeridas por la API CUA hasta que no se
    solicite ninguna acción más.
    """
    while True:
        # Se buscan llamadas de tipo 'computer_call'
        computer_calls = [item for item in response.get("output", []) if item.get("type") == "computer_call"]
        if not computer_calls:
            print("No se encontró ninguna llamada de computadora. Salida del modelo:")
            for item in response.get("output", []):
                print(item)
            break

        # Se toma la primera llamada (se asume una única acción por respuesta)
        computer_call = computer_calls[0]
        last_call_id = computer_call.get("call_id")
        action = computer_call.get("action", {})

        # Ejecutar la acción en el entorno del navegador
        handle_model_action(page, action)
        time.sleep(1)  # Espera para que la acción surta efecto

        # Captura el screenshot actualizado
        screenshot_bytes = get_screenshot(page)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Envía el screenshot de vuelta como output de la llamada de computadora
        response = client.responses.create(
            model="computer-use-preview",
            previous_response_id=response.get("id"),
            tools=[{
                "type": "computer_use_preview",
                "display_width": 1024,
                "display_height": 768,
                "environment": "browser"
            }],
            input=[{
                "call_id": last_call_id,
                "type": "computer_call_output",
                "output": {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{screenshot_base64}"
                }
            }],
            truncation="auto"
        )
    return response

def main():
    # Inicializamos Playwright y lanzamos el navegador
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            chromium_sandbox=True,
            env={},  # Ambiente aislado
            args=[
                "--disable-extensions",
                "--disable-file-system"
            ]
        )
        page = browser.new_page()
        page.set_viewport_size({"width": 1024, "height": 768})
        page.goto("https://bing.com")
        time.sleep(2)  # Tiempo para cargar la página

        # Inicializamos el cliente OpenAI
        client = OpenAI()

        # Enviamos la primera solicitud al modelo con la herramienta de computer use
        response = client.responses.create(
            model="computer-use-preview",
            tools=[{
                "type": "computer_use_preview",
                "display_width": 1024,
                "display_height": 768,
                "environment": "browser"
            }],
            input=[{
                "role": "user",
                "content": "Check the latest OpenAI news on bing.com."
            }],
            reasoning={
                "generate_summary": "concise"
            },
            truncation="auto"
        )
        print("Respuesta inicial del modelo:")
        print(response.get("output"))

        # Ejecutamos el bucle de interacción para procesar las acciones del modelo
        final_response = computer_use_loop(page, client, response)
        print("Respuesta final del modelo:")
        print(final_response)

        # Cerramos el navegador
        browser.close()

if __name__ == "__main__":
    main()
