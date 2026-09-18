const { test, expect } = require('@playwright/test');
const path = require('path');

function mockApi(page) {
  const state = {
    inventory: [
      { reference: 'Tools', item: 'Clé dynamométrique', quantity: 3, availability: '✓', barcode: 'TOOL-TORQUE-WRENCH', reorder_min: 1 },
      { reference: 'Station Parts', item: 'Filtre à huile KIA', quantity: 12, availability: '✓', barcode: 'KIA-OIL-FILTER', reorder_min: 4 },
    ],
    history: [],
    warranty: [],
  };

  return page.route('**/api/**', async (route, request) => {
    const pathname = new URL(request.url()).pathname;
    const method = request.method();

    if (pathname.endsWith('/inventory') && method === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, ...state }) });
      return;
    }

    if (pathname.endsWith('/auth/login/pin') && method === 'POST') {
      const payload = JSON.parse(request.postData() || '{}');
      if (payload.role_key === 'maintenance' && payload.pin === '7351') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
          ok: true, token: 'majdi-token', person: { name: 'Majdi', role: 'Maintenance', code: 'Majdi/Maintenance' },
        }) });
        return;
      }
      if (payload.role_key === 'management' && payload.pin === '4827') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
          ok: true, token: 'management-token', person: { name: 'Management', role: 'Management', code: 'Management/Management' },
        }) });
        return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'Code PIN incorrect. Réessayez.' }) });
      return;
    }

    if (pathname.endsWith('/take-batch') && method === 'POST') {
      const payload = JSON.parse(request.postData() || '{}');
      for (const entry of payload.items) {
        state.history.push({
          timestamp: new Date().toISOString(), personRole: `${payload.person}/${payload.role}`,
          item: entry.item, expectedReturn: entry.expectedReturn || 'None', returnedAt: 'Not returned',
          returnedBy: '', txId: `tx-${state.history.length + 1}`, qty: entry.qty || 1,
        });
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, txIds: state.history.map((h) => h.txId) }) });
      return;
    }

    if (pathname.endsWith('/return-batch') && method === 'POST') {
      const payload = JSON.parse(request.postData() || '{}');
      state.history = state.history.map((h) => payload.txIds.includes(h.txId)
        ? { ...h, returnedAt: new Date().toISOString(), returnedBy: payload.returnedBy }
        : h);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, returned: payload.txIds.length }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
}

async function enterPin(page, digits) {
  for (const digit of digits) await page.locator(`.numpad-key[data-digit="${digit}"]`).click();
  await page.getByRole('button', { name: 'Se connecter' }).click();
}

async function signInMajdi(page) {
  await page.getByText('Majdi', { exact: true }).click();
  await enterPin(page, '7351');
  await expect(page.getByText('Retirer du matériel')).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto(`file://${path.join(__dirname, 'index.html')}`);
});

test('affiche uniquement les deux profils autorisés', async ({ page }) => {
  await expect(page.getByText('Management', { exact: true })).toBeVisible();
  await expect(page.getByText('Majdi', { exact: true })).toBeVisible();
  await expect(page.getByText('Maintenance', { exact: true })).toHaveCount(0);
});

test('connexion Majdi avec un PIN à quatre chiffres', async ({ page }) => {
  await signInMajdi(page);
  await expect(page.getByRole('button', { name: 'Rapport de gestion' })).toHaveCount(0);
});

test('sortie puis retour d’un outil', async ({ page }) => {
  await signInMajdi(page);
  await page.getByText('Retirer du matériel').click();
  await page.getByRole('button', { name: 'Ou choisir manuellement' }).click();
  await page.getByText('Outils', { exact: true }).click();
  await page.getByText('Clé dynamométrique', { exact: true }).click();
  await page.getByRole('button', { name: 'Confirmer' }).click();
  await page.getByRole('button', { name: /Confirmer le retrait/ }).click();
  await expect(page.getByText(/article\(s\) enregistré\(s\)/)).toBeVisible();
});

test('le rapport est réservé au profil Management', async ({ page }) => {
  await page.getByText('Management', { exact: true }).click();
  await enterPin(page, '4827');
  await page.getByRole('button', { name: 'Rapport de gestion' }).click();
  await expect(page.getByRole('button', { name: /Ouverts/ })).toBeVisible();
  await page.getByRole('button', { name: 'État du stock' }).click();
  await expect(page.getByText('Pièces de poste')).toBeVisible();
});
