/* Stockage local (IndexedDB) de la caisse — phases 2 et 3.
 *
 * "produits"/"meta"  : copie persistante du catalogue + horodatage de
 *                      dernière synchronisation (phase 2).
 * "ventes_attente"    : ventes créées hors-ligne, en attente d'envoi au
 *                      serveur (phase 3). Le stock n'est jamais vérifié
 *                      avant la mise en file, ni ici ni côté serveur.
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

  async function compterVentesConflit() {
    const ventes = await listerVentesAttente();
    return ventes.filter((v) => v.statut === "conflit").length;
  }

  /** Marque une vente en conflit après un refus du serveur à la
   * synchronisation — jamais supprimée automatiquement, seule une
   * personne (gérance) tranche ce qu'il faut en faire. */
  async function marquerVenteConflit(uuid, erreur) {
    const db = await ouvrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("ventes_attente", "readwrite");
      const store = tx.objectStore("ventes_attente");
      store.get(uuid).onsuccess = (evt) => {
        const vente = evt.target.result;
        if (vente) {
          vente.statut = "conflit";
          vente.erreur = erreur;
          store.put(vente);
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  window.AquapiloDB = {
    sauvegarderCatalogue, chargerCatalogue,
    ajouterVenteAttente, listerVentesAttente, supprimerVenteAttente,
    compterVentesEnAttente, compterVentesConflit, marquerVenteConflit,
  };
})();
