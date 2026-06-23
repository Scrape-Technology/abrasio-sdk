"""
Client certificate login example (e.g. ICP-Brasil digital certificate on gov.br).

Demonstrates `Abrasio.route_with_certificate(...)`: intercepts the certificate-login
request and replays it outside the browser using httpx (which supports TLS client
certificates natively), then fulfills the route with the real response.

Works in both local and cloud mode, unlike Playwright's native `client_certificates`
option (local mode only) - see README.md "Client Certificates" section for why.

Before running:
    pip install abrasio[cert]   # cryptography, needed to convert PFX -> PEM
    export ABRASIO_API_KEY=sk_live_xxx
    export DEMO_CERT_PFX_PATH=/path/to/certificado.pfx
    export DEMO_CERT_PASSPHRASE=...
"""

import asyncio
import os

from abrasio import Abrasio, build_client_certificate


async def main():
    api_key = os.getenv("ABRASIO_API_KEY")
    if not api_key:
        print("Set ABRASIO_API_KEY environment variable to use cloud mode")
        print("Example: export ABRASIO_API_KEY=sk_live_xxx")
        return

    pfx_path = os.getenv("DEMO_CERT_PFX_PATH") or input("Path to the .pfx certificate: ")
    passphrase = os.getenv("DEMO_CERT_PASSPHRASE") or input("Certificate passphrase: ")

    cert = build_client_certificate(
        origin="https://login.esocial.gov.br",
        pfx_path=pfx_path,
        passphrase=passphrase,
    )

    async with Abrasio(api_key=api_key, region="br") as browser:
        page = await browser.new_page()
        await page.goto("https://login.esocial.gov.br/login.aspx")
        await page.locator('//*[@id="login-acoes"]/div[2]/p/button').click()
        await page.wait_for_load_state()

        await page.evaluate('document.getElementById("operation-field").setAttribute("name", "operation");')
        await page.evaluate('document.getElementById("operation-field").setAttribute("value", "login-certificate");')

        certificate_button = page.locator('//*[@id="login-certificate"]')
        form_action = await certificate_button.get_attribute("formaction")
        await page.evaluate(f"document.getElementById('loginData').setAttribute('action','{form_action}')")

        # Intercept the certificate-login submission and replay it outside the
        # browser with the client certificate attached, via httpx.
        await browser.route_with_certificate(page, form_action, cert)

        await certificate_button.click()
        await page.wait_for_load_state()
        print("Logged in:", page.url)


if __name__ == "__main__":
    asyncio.run(main())
