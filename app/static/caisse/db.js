/* Stockage local (IndexedDB) de la caisse — phases 2 et 3.
 *
 * "produits"/"meta"  : copie persistante du catalogue + horodatage de
 *                      dernière synchronisation (phase 2).
 * "ventes_attente"    : ventes créées hors-ligne, en attente d'envoi au
 *                      serveur (phase 3). Le stock "local effectif" d'un
 *                      produit est le stock connu du catalogue MOINS les
 *                      quantités déjà mises en file pour ce produit dans
 *                      la même boutique — pour ne jamais vendre deux fois
 *                      le même dernier kilo depuis le même appareil avant
 *                      la synchronisation.
 */
(function () {
  const NOM_DB = "aquapilo-caisse";
  const VERSION_DB = 2;

  function ouvrirDB() {
    return new Promise((resolve, reject) => {
      const requete = indexedDB.open(NOM_DB, VERSION_DB);
      requete.onupgradeneeded = (evt) => {
        const db = evt.target.result;
        if (!db.objectStoreNames.contains("produits")) {
          db.createObjectStore("produits", { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains("meta")) {
          db.createObjectStore("meta", { keyPath: "cle" });
        }
        if (!db.objectStoreNames.contains("ventes_attente")) {
          db.createObjectStore("ventes_attente", { keyPath: "uuid" });
        }
      };
      requete.onsuccess = () => resolve(requete.result);
      requete.onerror = () => reject(requete.error);
    });
  }

  async function sauvegarderCatalogue({ produits, boutiques, modes, boutiqueFixe, prixModifiable }) {
    const db = await ouvrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(["produits", "meta"], "readwrite");
      const storeProduits = tx.objectStore("produits");
      storeProduits.clear();
      produits.forEach((p) => storeProduits.put(p));
      const storeMeta = tx.objectStore("meta");
      storeMeta.put({ cle: "contexte", boutiques, modes, boutiqueFixe, prixModifiable });
      storeMeta.put({ cle: "derniere_maj", valeur: Date.now() });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function chargerCatalogue() {
    const db = await ouvrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(["produits", "meta"], "readonly");
      const produits = [];
      tx.objectStore("produits").openCursor().onsuccess = (evt) => {
        const curseur = evt.target.result;
        if (curseur) {
          produits.push(curseur.value);
          curseur.continue();
        }
      };
      let contexte = null;
      let derniereMaj = null;
      const storeMeta = tx.objectStore("meta");
      storeMeta.get("contexte").onsuccess = (evt) => { contexte = evt.target.result || null; };
      storeMeta.get("derniere_maj").onsuccess = (evt) => {
        derniereMaj = evt.target.result ? evt.target.result.valeur : null;
      };
      tx.oncomplete = () => resolve({ produits, contexte, derniereMaj });
      tx.onerror = () => reject(tx.error);
    });
  }

  // ---------- Ventes en attente (phase 3) ----------

  async function ajouterVenteAttente(vente) {
    const db = await ouvrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("ventes_attente", "readwrite");
      tx.objectStore("ventes_attente").put(vente);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function listerVentesAttente() {
    const db = await ouvrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("ventes_attente", "readonly");
      const ventes = [];
      tx.objectStore("ventes_attente").openCursor().onsuccess = (evt) => {
        const curseur = evt.target.result;
        if (curseur) { ventes.push(curseur.value); curseur.continue(); }
      };
      tx.oncomplete = () => resolve(ventes);
      tx.onerror = () => reject(tx.error);
    });
  }

  async function supprimerVenteAttente(uuid) {
    const db = await ouvrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("ventes_attente", "readwrite");
      tx.objectStore("ventes_attente").delete(uuid);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function compterVentesEnAttente() {
    const ventes = await listerVentesAttente();
    return ventes.filter((v) => v.statut === "en_attente").length;
  }

  /** Stock du produit dans la boutique, moins les quantités déjà mises
   * en file d'attente (non encore synchronisées) sur cet appareil. */
  async function stockLocalEffectif(produitId, boutiqueId) {
    const [{ produits }, ventes] = await Promise.all([
      chargerCatalogue(), listerVentesAttente(),
    ]);
    const produit = produits.find((p) => p.id === produitId);
    const stockCatalogue = produit ? (produit.stocks[boutiqueId] ?? 0) : 0;
    const dejaEnAttente = ventes
      .filter((v) => v.statut === "en_attente" && v.boutiqueId === boutiqueId)
      .flatMap((v) => v.lignes)
      .filter((l) => l.produit_id === produitId)
      .reduce((somme, l) => somme + l.quantite, 0);
    return stockCatalogue - dejaEnAttente;
  }

  window.AquapiloDB = {
    sauvegarderCatalogue, chargerCatalogue,
    ajouterVenteAttente, listerVentesAttente, supprimerVenteAttente,
    compterVentesEnAttente, stockLocalEffectif,
  };
})();
