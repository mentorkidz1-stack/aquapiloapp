/* Stockage local (IndexedDB) du catalogue de la caisse — phase 2.
 *
 * Rôle : garder une copie persistante et interrogeable du catalogue
 * (produits, boutiques, modes de paiement) au-delà d'un simple
 * rechargement de page, avec un horodatage de dernière synchronisation.
 * Base pour la phase 3 (file d'attente des ventes hors-ligne, qui devra
 * décrémenter le stock local au fil des ventes en attente).
 */
(function () {
  const NOM_DB = "aquapilo-caisse";
  const VERSION_DB = 1;

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

  window.AquapiloDB = { sauvegarderCatalogue, chargerCatalogue };
})();
