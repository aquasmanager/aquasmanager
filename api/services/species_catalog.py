"""
Jeu de départ du catalogue d'espèces : poissons (mer et eau douce),
coraux, plantes et invertébrés.

Valeurs indicatives issues de connaissances générales (taille adulte,
volume minimal conseillé, compatibilité récif...) : à vérifier et corriger
au besoin depuis l'interface. Les coraux utilisent les échelles 1-10 de la
fiche corail (lumière 1-15 : 1 = 50 PAR ; brassage ; agressivité ; résistance,
10 = très robuste ; placement, 1 = fond, 10 = haut du bac) ; les plantes
celles de la fiche plante (lumière 1-10, température °C, hauteur cm).
"""

import logging

from sqlalchemy.orm import Session

from models.aquarium import AquariumWaterType
from models.coral import CoralType
from models.plant import PlantGrowing, PlantLocation
from models.species import CoralSpecies, FishSpecies, InvertebrateCategory, InvertebrateSpecies, PlantSpecies

logger = logging.getLogger(__name__)

# (nom courant, nom scientifique, famille, origine, taille max cm, volume min L, compatible récif, note)
MARINE_FISH_SPECIES = [
    ("Poisson-clown ocellaris", "Amphiprion ocellaris", "Pomacentridae", "Indo-Pacifique", 11, 100, True, None),
    ("Poisson-clown percula", "Amphiprion percula", "Pomacentridae", "Pacifique Ouest", 11, 100, True, None),
    ("Poisson-clown de Clark", "Amphiprion clarkii", "Pomacentridae", "Indo-Pacifique", 15, 150, True, None),
    ("Poisson-clown tomate", "Amphiprion frenatus", "Pomacentridae", "Pacifique Ouest", 14, 150, True, "Peut être territorial."),
    ("Poisson-clown marron", "Premnas biaculeatus", "Pomacentridae", "Indo-Pacifique Ouest", 17, 200, True, "Territorial, surtout la femelle."),
    ("Demoiselle bleue", "Chrysiptera cyanea", "Pomacentridae", "Indo-Pacifique", 8, 100, True, "Territoriale."),
    ("Demoiselle à queue jaune", "Chrysiptera parasema", "Pomacentridae", "Pacifique Ouest", 7, 80, True, None),
    ("Demoiselle à trois bandes", "Dascyllus aruanus", "Pomacentridae", "Indo-Pacifique", 10, 150, True, "Agressive en grandissant."),
    ("Chromis vert", "Chromis viridis", "Pomacentridae", "Indo-Pacifique", 10, 200, True, "À maintenir en groupe."),
    ("Gramma royal", "Gramma loreto", "Grammatidae", "Caraïbes", 8, 100, True, None),
    ("Pseudochromis de Fridman", "Pseudochromis fridmani", "Pseudochromidae", "Mer Rouge", 7, 100, True, None),
    ("Gobie néon", "Elacatinus oceanops", "Gobiidae", "Atlantique Ouest", 5, 40, True, None),
    ("Poisson de feu", "Nemateleotris magnifica", "Microdesmidae", "Indo-Pacifique", 9, 100, True, "Sauteur : couvrir le bac."),
    ("Gobie gardien jaune", "Cryptocentrus cinctus", "Gobiidae", "Pacifique Ouest", 8, 80, True, "Vit en symbiose avec une crevette Alpheus."),
    ("Gobie de Yasha", "Stonogobiops yasha", "Gobiidae", "Pacifique Ouest", 5, 40, True, None),
    ("Gobie dormeur à tête dorée", "Valenciennea strigata", "Gobiidae", "Indo-Pacifique", 18, 300, True, "Remue le sable."),
    ("Poisson-mâchoire à tête jaune", "Opistognathus aurifrons", "Opistognathidae", "Caraïbes", 10, 150, True, "Besoin d'un substrat profond ; sauteur."),
    ("Dragonnet mandarin", "Synchiropus splendidus", "Callionymidae", "Pacifique Ouest", 7, 200, True, "Bac mature riche en microfaune."),
    ("Blennie bicolore", "Ecsenius bicolor", "Blenniidae", "Indo-Pacifique", 11, 100, True, None),
    ("Blennie Midas", "Ecsenius midas", "Blenniidae", "Indo-Pacifique", 13, 150, True, None),
    ("Blennie tondeuse", "Salarias fasciatus", "Blenniidae", "Indo-Pacifique", 14, 150, True, "Brouteur d'algues."),
    ("Cardinal de Banggai", "Pterapogon kauderni", "Apogonidae", "Indonésie", 8, 100, True, None),
    ("Cardinal pyjama", "Sphaeramia nematoptera", "Apogonidae", "Pacifique Ouest", 8, 100, True, None),
    ("Anthias squamipinnis", "Pseudanthias squamipinnis", "Serranidae", "Indo-Pacifique", 15, 400, True, "Groupe, nourrir plusieurs fois par jour."),
    ("Labre à six lignes", "Pseudocheilinus hexataenia", "Labridae", "Indo-Pacifique", 8, 100, True, None),
    ("Labre nettoyeur", "Labroides dimidiatus", "Labridae", "Indo-Pacifique", 14, 300, True, "Difficile à nourrir en captivité."),
    ("Labre fée de Carpenter", "Paracheilinus carpenteri", "Labridae", "Pacifique Ouest", 8, 200, True, "Sauteur : couvrir le bac."),
    ("Labre fée de Solor", "Cirrhilabrus solorensis", "Labridae", "Indonésie", 11, 250, True, "Sauteur : couvrir le bac."),
    ("Labre doré", "Halichoeres chrysus", "Labridae", "Indo-Pacifique Ouest", 12, 250, True, "S'enfouit dans le sable la nuit."),
    ("Coris gaimard", "Coris gaimard", "Labridae", "Indo-Pacifique", 40, 600, False, "Mange crustacés et mollusques."),
    ("Chirurgien jaune", "Zebrasoma flavescens", "Acanthuridae", "Pacifique (Hawaï)", 20, 400, True, None),
    ("Chirurgien brun", "Zebrasoma scopas", "Acanthuridae", "Indo-Pacifique", 20, 400, True, None),
    ("Chirurgien de Mer Rouge", "Zebrasoma xanthurum", "Acanthuridae", "Mer Rouge", 25, 500, True, "Territorial envers les autres chirurgiens."),
    ("Chirurgien voilier", "Zebrasoma veliferum", "Acanthuridae", "Indo-Pacifique", 40, 750, True, None),
    ("Chirurgien bleu", "Paracanthurus hepatus", "Acanthuridae", "Indo-Pacifique", 31, 600, True, "Sensible aux maladies (ich)."),
    ("Chirurgien à poitrine blanche", "Acanthurus leucosternon", "Acanthuridae", "Océan Indien", 23, 500, True, "Sensible aux maladies (ich)."),
    ("Chirurgien Kole", "Ctenochaetus strigosus", "Acanthuridae", "Pacifique (Hawaï)", 18, 300, True, "Brouteur de diatomées."),
    ("Nason à éperons orange", "Naso lituratus", "Acanthuridae", "Indo-Pacifique", 46, 1000, True, "Grand nageur."),
    ("Ange de Lamarck", "Genicanthus lamarck", "Pomacanthidae", "Indo-Pacifique Ouest", 25, 500, True, "Planctonophage, compatible récif."),
    ("Ange flamme", "Centropyge loricula", "Pomacanthidae", "Pacifique", 15, 250, False, "Peut picorer LPS et bénitiers."),
    ("Ange nain bicolore", "Centropyge bicolor", "Pomacanthidae", "Indo-Pacifique", 15, 250, False, "Peut picorer LPS et bénitiers."),
    ("Poisson-faucon flamme", "Neocirrhites armatus", "Cirrhitidae", "Pacifique", 9, 150, True, "Peut chasser les petites crevettes."),
    ("Poisson-lapin renard", "Siganus vulpinus", "Siganidae", "Pacifique Ouest", 25, 500, True, "Épines venimeuses."),
    ("Papillon à long nez", "Forcipiger flavissimus", "Chaetodontidae", "Indo-Pacifique", 22, 400, False, "Picore vers tubicoles et polypes."),
    ("Papillon à bec", "Chelmon rostratus", "Chaetodontidae", "Pacifique Ouest", 20, 400, False, "Mange les aiptasias, peut picorer les coraux."),
    ("Canthigaster de Valentin", "Canthigaster valentini", "Tetraodontidae", "Indo-Pacifique", 11, 150, False, "Mange invertébrés et coraux mous."),
    ("Baliste bleu", "Odonus niger", "Balistidae", "Indo-Pacifique", 50, 800, False, "Mange crustacés ; peut devenir agressif."),
    ("Rascasse zèbre naine", "Dendrochirus zebra", "Scorpaenidae", "Indo-Pacifique", 25, 300, False, "Venimeux ; mange petits poissons et crevettes."),
]

# (nom courant, nom scientifique, type, famille, origine, lumière min, max, brassage min, max,
#  agressivité, résistance, placement, note)
CORAL_SPECIES = [
    ("Acropora millepora", "Acropora millepora", "SPS", "Acroporidae", "Indo-Pacifique", 6, 12, 6, 9, 3, 3, 8, "Paramètres très stables requis."),
    ("Acropora tenuis", "Acropora tenuis", "SPS", "Acroporidae", "Indo-Pacifique", 6, 12, 6, 9, 3, 3, 8, None),
    ("Acropora formosa", "Acropora formosa", "SPS", "Acroporidae", "Indo-Pacifique", 6, 12, 6, 9, 3, 4, 8, None),
    ("Montipora digitata", "Montipora digitata", "SPS", "Acroporidae", "Indo-Pacifique", 4, 10, 4, 7, 2, 7, 6, "Bon SPS de départ."),
    ("Montipora capricornis", "Montipora capricornis", "SPS", "Acroporidae", "Indo-Pacifique", 4, 8, 3, 6, 2, 7, 5, "Croissance en plaques."),
    ("Montipora confusa", "Montipora confusa", "SPS", "Acroporidae", "Indo-Pacifique", 4, 8, 4, 6, 2, 6, 6, None),
    ("Pocillopora", "Pocillopora damicornis", "SPS", "Pocilloporidae", "Indo-Pacifique", 4, 10, 5, 8, 3, 7, 7, None),
    ("Seriatopora", "Seriatopora hystrix", "SPS", "Pocilloporidae", "Indo-Pacifique", 4, 10, 5, 8, 2, 5, 7, None),
    ("Stylophora", "Stylophora pistillata", "SPS", "Pocilloporidae", "Indo-Pacifique", 4, 10, 5, 8, 2, 6, 7, None),
    ("Euphyllia marteau", "Euphyllia paraancora", "LPS", "Euphylliidae", "Indo-Pacifique", 2, 6, 3, 5, 6, 6, 4, "Tentacules urticants : prévoir de l'espace."),
    ("Euphyllia gold", "Euphyllia paraancora", "LPS", "Euphylliidae", "Indo-Pacifique", 4, 10, 2, 5, 5, 7, 3, "Variété dorée de l'Euphyllia marteau."),
    ("Euphyllia ancre", "Euphyllia ancora", "LPS", "Euphylliidae", "Indo-Pacifique", 2, 6, 3, 5, 6, 6, 4, "Tentacules urticants : prévoir de l'espace."),
    ("Euphyllia torche", "Euphyllia glabrescens", "LPS", "Euphylliidae", "Indo-Pacifique", 2, 6, 3, 5, 7, 5, 4, "Tentacules balayeurs longs."),
    ("Euphyllia divisa", "Euphyllia divisa", "LPS", "Euphylliidae", "Indo-Pacifique", 2, 6, 3, 5, 6, 6, 4, None),
    ("Duncan", "Duncanopsammia axifuga", "LPS", "Dendrophylliidae", "Australie", 2, 4, 2, 4, 3, 8, 3, "Très robuste, se nourrit volontiers."),
    ("Caulastrea trompette", "Caulastrea furcata", "LPS", "Merulinidae", "Indo-Pacifique", 2, 6, 2, 4, 3, 8, 4, None),
    ("Favia", "Dipsastraea speciosa", "LPS", "Merulinidae", "Indo-Pacifique", 2, 6, 2, 4, 6, 8, 3, "Tentacules nocturnes urticants."),
    ("Acanthastrea lordhowensis", "Micromussa lordhowensis", "LPS", "Lobophylliidae", "Australie", 2, 4, 2, 4, 5, 7, 2, None),
    ("Lobophyllia", "Lobophyllia hemprichii", "LPS", "Lobophylliidae", "Indo-Pacifique", 2, 4, 2, 4, 5, 7, 2, None),
    ("Blastomussa", "Blastomussa wellsi", "LPS", "Lobophylliidae", "Indo-Pacifique", 2, 4, 1, 3, 2, 7, 2, None),
    ("Cynarina", "Cynarina lacrymalis", "LPS", "Lobophylliidae", "Indo-Pacifique", 2, 4, 1, 3, 4, 6, 1, "À poser sur le sable."),
    ("Scolymia", "Homophyllia australis", "LPS", "Lobophylliidae", "Australie", 2, 4, 1, 3, 4, 5, 1, "À poser sur le sable."),
    ("Trachyphyllia", "Trachyphyllia geoffroyi", "LPS", "Merulinidae", "Indo-Pacifique", 2, 4, 1, 3, 4, 6, 1, "À poser sur le sable."),
    ("Fungia", "Fungia fungites", "LPS", "Fungiidae", "Indo-Pacifique", 2, 4, 1, 3, 4, 6, 1, "Corail libre, sur le sable."),
    ("Galaxea", "Galaxea fascicularis", "LPS", "Euphylliidae", "Indo-Pacifique", 2, 6, 3, 5, 8, 7, 4, "Très agressif la nuit."),
    ("Turbinaria", "Turbinaria reniformis", "LPS", "Dendrophylliidae", "Indo-Pacifique", 4, 8, 3, 6, 2, 8, 5, None),
    ("Corail bulle", "Plerogyra sinuosa", "LPS", "Plerogyridae", "Indo-Pacifique", 2, 4, 1, 3, 6, 6, 3, "Bulles fragiles, brassage doux."),
    ("Corail élégant", "Catalaphyllia jardinei", "LPS", "Euphylliidae", "Indo-Pacifique", 2, 6, 1, 3, 6, 4, 1, "À poser sur le sable."),
    ("Zoanthus", "Zoanthus sp.", "MOU", "Zoanthidae", "Indo-Pacifique", 2, 6, 2, 5, 3, 9, 4, "Très robuste, prolifère."),
    ("Palythoa", "Palythoa sp.", "MOU", "Sphenopidae", "Indo-Pacifique", 2, 6, 2, 5, 4, 9, 3, "Palytoxine : gants obligatoires."),
    ("Discosoma", "Discosoma sp.", "MOU", "Discosomidae", "Indo-Pacifique", 2, 4, 1, 3, 4, 9, 2, "Peut envahir le bac."),
    ("Rhodactis", "Rhodactis sp.", "MOU", "Discosomidae", "Indo-Pacifique", 2, 4, 1, 3, 5, 9, 2, None),
    ("Ricordea", "Ricordea florida", "MOU", "Ricordeidae", "Caraïbes", 2, 4, 1, 3, 3, 7, 2, None),
    ("Sarcophyton", "Sarcophyton sp.", "MOU", "Alcyoniidae", "Indo-Pacifique", 2, 6, 3, 6, 6, 9, 3, "Libère des terpènes : charbon actif conseillé."),
    ("Sinularia", "Sinularia sp.", "MOU", "Alcyoniidae", "Indo-Pacifique", 2, 6, 3, 6, 5, 9, 4, None),
    ("Lobophytum", "Lobophytum sp.", "MOU", "Alcyoniidae", "Indo-Pacifique", 2, 6, 3, 6, 5, 9, 3, None),
    ("Arbre du Kenya", "Capnella imbricata", "MOU", "Nephtheidae", "Indo-Pacifique", 2, 4, 3, 5, 4, 9, 4, "Se bouture seul, peut envahir."),
    ("Xenia", "Xenia sp.", "MOU", "Xeniidae", "Indo-Pacifique", 2, 6, 2, 5, 3, 9, 4, "Peut envahir le bac."),
    ("GSP (étoile verte)", "Briareum violaceum", "MOU", "Briareidae", "Indo-Pacifique", 2, 6, 3, 6, 5, 10, 3, "Envahissant : isoler sur un rocher."),
]


# Eau douce : (nom courant, nom scientifique, famille, origine, taille max cm, volume min L, note)
FRESHWATER_FISH_SPECIES = [
    ("Néon bleu", "Paracheirodon innesi", "Characidae", "Amérique du Sud", 4, 60, "En groupe d'au moins 10."),
    ("Néon cardinalis", "Paracheirodon axelrodi", "Characidae", "Amérique du Sud", 5, 80, "En groupe ; eau douce et acide."),
    ("Nez rouge", "Petitella bleheri", "Characidae", "Amérique du Sud", 5, 80, "En groupe."),
    ("Tétra ember", "Hyphessobrycon amandae", "Characidae", "Brésil", 2, 40, "En groupe."),
    ("Tétra serpae", "Hyphessobrycon eques", "Characidae", "Amérique du Sud", 4, 80, "Peut pincer les nageoires."),
    ("Tétra noir", "Gymnocorymbus ternetzi", "Characidae", "Amérique du Sud", 6, 80, None),
    ("Rasbora arlequin", "Trigonostigma heteromorpha", "Danionidae", "Asie du Sud-Est", 5, 60, "En groupe."),
    ("Danio zébré", "Danio rerio", "Danionidae", "Asie du Sud", 5, 60, "Très actif, en groupe."),
    ("Néon du pauvre", "Tanichthys albonubes", "Danionidae", "Chine", 4, 50, "Eau fraîche (18-22 °C)."),
    ("Barbus de Sumatra", "Puntigrus tetrazona", "Cyprinidae", "Indonésie", 7, 80, "Pince les nageoires des poissons lents."),
    ("Barbus cerise", "Puntius titteya", "Cyprinidae", "Sri Lanka", 5, 60, None),
    ("Mangeur d'algues siamois", "Crossocheilus oblongus", "Cyprinidae", "Asie du Sud-Est", 15, 150, "Mange les algues filamenteuses."),
    ("Poisson rouge", "Carassius auratus", "Cyprinidae", "Asie de l'Est", 30, 200, "Eau froide ; bassin conseillé."),
    ("Guppy", "Poecilia reticulata", "Poeciliidae", "Amérique du Sud", 6, 54, "Vivipare prolifique."),
    ("Platy", "Xiphophorus maculatus", "Poeciliidae", "Amérique centrale", 6, 60, "Vivipare."),
    ("Molly", "Poecilia sphenops", "Poeciliidae", "Amérique centrale", 10, 100, "Vivipare, apprécie une eau dure."),
    ("Porte-épée", "Xiphophorus hellerii", "Poeciliidae", "Amérique centrale", 14, 120, "Vivipare."),
    ("Combattant", "Betta splendens", "Osphronemidae", "Asie du Sud-Est", 7, 20, "Un seul mâle par bac."),
    ("Gourami nain", "Trichogaster lalius", "Osphronemidae", "Asie du Sud", 8, 60, None),
    ("Gourami perlé", "Trichopodus leerii", "Osphronemidae", "Asie du Sud-Est", 12, 150, None),
    ("Scalaire", "Pterophyllum scalare", "Cichlidae", "Amérique du Sud", 15, 200, "Mange les petits poissons (néons)."),
    ("Discus", "Symphysodon aequifasciatus", "Cichlidae", "Amazonie", 20, 300, "Exigeant : eau chaude, douce et très propre."),
    ("Ramirezi", "Mikrogeophagus ramirezi", "Cichlidae", "Amérique du Sud", 7, 80, "Eau chaude (27-30 °C)."),
    ("Apistogramma cacatuoides", "Apistogramma cacatuoides", "Cichlidae", "Amérique du Sud", 8, 80, None),
    ("Kribensis", "Pelvicachromis pulcher", "Cichlidae", "Afrique de l'Ouest", 10, 100, "Territorial en reproduction."),
    ("Cichlidé jaune du Malawi", "Labidochromis caeruleus", "Cichlidae", "Lac Malawi", 10, 200, "Eau dure ; bac spécifique Malawi."),
    ("Corydoras bronze", "Corydoras aeneus", "Callichthyidae", "Amérique du Sud", 7, 60, "En groupe, sol sableux."),
    ("Corydoras panda", "Corydoras panda", "Callichthyidae", "Pérou", 5, 60, "En groupe, sol sableux."),
    ("Otocinclus", "Otocinclus vittatus", "Loricariidae", "Amérique du Sud", 4, 60, "Mange les algues ; en groupe."),
    ("Ancistrus", "Ancistrus cirrhosus", "Loricariidae", "Amérique du Sud", 13, 100, "Besoin de bois à râper."),
    ("Loche clown", "Chromobotia macracanthus", "Botiidae", "Indonésie", 30, 400, "En groupe ; grand bac."),
    ("Kuhli", "Pangio kuhlii", "Cobitidae", "Asie du Sud-Est", 10, 60, "Nocturne, sol sableux."),
]

# (nom courant, nom scientifique, famille, origine, lumière min, max (1-10), température min, max (°C),
#  croissance, résistance, hauteur max cm, emplacement, note)
PLANT_SPECIES = [
    ("Anubias nana", "Anubias barteri nana", "Araceae", "Afrique de l'Ouest", 1, 4, 22, 28, "slow", 10, 10, "front", "À fixer sur roche ou racine, ne pas enterrer le rhizome."),
    ("Fougère de Java", "Microsorum pteropus", "Polypodiaceae", "Asie du Sud-Est", 1, 4, 20, 28, "slow", 10, 30, "middle", "Épiphyte : à fixer sur un support."),
    ("Bolbitis", "Bolbitis heudelotii", "Lomariopsidaceae", "Afrique", 2, 5, 22, 28, "slow", 7, 40, "back", "Épiphyte, aime le courant."),
    ("Bucephalandra", "Bucephalandra sp.", "Araceae", "Bornéo", 1, 5, 22, 28, "slow", 8, 10, "front", "Épiphyte."),
    ("Mousse de Java", "Taxiphyllum barbieri", "Hypnaceae", "Asie du Sud-Est", 1, 5, 18, 30, "average", 10, 10, "front", None),
    ("Cryptocoryne wendtii", "Cryptocoryne wendtii", "Araceae", "Sri Lanka", 1, 5, 22, 28, "slow", 8, 15, "front", "Peut fondre après plantation, repousse ensuite."),
    ("Cryptocoryne parva", "Cryptocoryne parva", "Araceae", "Sri Lanka", 3, 6, 22, 28, "slow", 6, 5, "front", None),
    ("Échinodorus (Amazone)", "Echinodorus bleheri", "Alismataceae", "Amérique du Sud", 3, 6, 22, 28, "average", 8, 50, "back", "Plante de fond imposante."),
    ("Sagittaire", "Sagittaria subulata", "Alismataceae", "Amérique", 3, 6, 20, 28, "average", 8, 20, "front", None),
    ("Vallisnérie", "Vallisneria spiralis", "Hydrocharitaceae", "Europe / Afrique", 3, 6, 18, 28, "fast", 9, 50, "back", "Se multiplie par stolons."),
    ("Élodée dense", "Egeria densa", "Hydrocharitaceae", "Amérique du Sud", 3, 7, 16, 26, "fast", 10, 50, "back", None),
    ("Grenouillette", "Limnobium laevigatum", "Hydrocharitaceae", "Amérique", 3, 7, 18, 28, "fast", 9, 5, "front", "Plante flottante."),
    ("Cornifle", "Ceratophyllum demersum", "Ceratophyllaceae", "Cosmopolite", 2, 6, 15, 28, "fast", 10, 50, "back", "Flottante ou lestée, absorbe les nitrates."),
    ("Lentille d'eau", "Lemna minor", "Araceae", "Cosmopolite", 3, 7, 10, 30, "fast", 10, 1, "front", "Flottante, très envahissante."),
    ("Hygrophila polysperma", "Hygrophila polysperma", "Acanthaceae", "Asie du Sud", 3, 7, 20, 28, "fast", 9, 40, "back", None),
    ("Hygrophila difformis", "Hygrophila difformis", "Acanthaceae", "Asie du Sud-Est", 3, 7, 22, 28, "fast", 9, 50, "back", None),
    ("Staurogyne repens", "Staurogyne repens", "Acanthaceae", "Brésil", 4, 7, 20, 28, "slow", 7, 10, "front", None),
    ("Limnophila", "Limnophila sessiliflora", "Plantaginaceae", "Asie du Sud-Est", 4, 7, 22, 28, "fast", 8, 50, "back", None),
    ("Rotala rotundifolia", "Rotala rotundifolia", "Lythraceae", "Asie du Sud-Est", 5, 8, 22, 28, "fast", 6, 40, "back", "Rougit sous forte lumière."),
    ("Ludwigia repens", "Ludwigia repens", "Onagraceae", "Amérique du Nord", 5, 8, 20, 28, "average", 7, 40, "back", None),
    ("Alternanthera reineckii", "Alternanthera reineckii", "Amaranthaceae", "Amérique du Sud", 6, 9, 22, 28, "average", 5, 40, "middle", "Couleur rouge, CO2 conseillé."),
    ("Cabomba", "Cabomba caroliniana", "Cabombaceae", "Amérique", 6, 9, 22, 28, "fast", 4, 50, "back", None),
    ("Lotus tigre", "Nymphaea lotus", "Nymphaeaceae", "Afrique", 4, 7, 22, 28, "fast", 7, 50, "middle", "Feuilles flottantes à tailler."),
    ("Pogostemon helferi", "Pogostemon helferi", "Lamiaceae", "Thaïlande", 5, 8, 22, 28, "slow", 5, 10, "front", None),
    ("Éléocharis", "Eleocharis acicularis", "Cyperaceae", "Cosmopolite", 5, 8, 18, 28, "average", 6, 15, "front", "Gazon, CO2 conseillé."),
    ("Monte Carlo", "Micranthemum tweediei", "Linderniaceae", "Argentine", 6, 9, 20, 28, "average", 4, 3, "front", "Tapis, CO2 conseillé."),
    ("Hemianthus cuba", "Hemianthus callitrichoides", "Linderniaceae", "Cuba", 7, 10, 20, 26, "average", 2, 3, "front", "Tapis, CO2 indispensable."),
    ("Glossostigma", "Glossostigma elatinoides", "Phrymaceae", "Australie", 7, 10, 20, 26, "fast", 2, 3, "front", "Tapis, CO2 indispensable."),
]

# (nom courant, nom scientifique, famille, origine, eau, catégorie, compatible récif, volume min L, note)
INVERTEBRATE_SPECIES = [
    ("Crevette nettoyeuse", "Lysmata amboinensis", "Lysmatidae", "Indo-Pacifique", "sea", "shrimp", True, 60, "Nettoie les poissons."),
    ("Crevette sang", "Lysmata debelius", "Lysmatidae", "Indo-Pacifique", "sea", "shrimp", True, 60, None),
    ("Crevette peppermint", "Lysmata wurdemanni", "Lysmatidae", "Atlantique Ouest", "sea", "shrimp", True, 60, "Mange les aiptasias."),
    ("Crevette pistolet", "Alpheus randalli", "Alpheidae", "Indo-Pacifique", "sea", "shrimp", True, 40, "Symbiose avec un gobie gardien."),
    ("Crevette arlequin", "Hymenocera picta", "Hymenoceridae", "Indo-Pacifique", "sea", "shrimp", True, 60, "Se nourrit uniquement d'étoiles de mer."),
    ("Bernard-l'ermite bleu", "Clibanarius tricolor", "Diogenidae", "Caraïbes", "sea", "crab", True, 40, "Prévoir des coquilles vides."),
    ("Crabe émeraude", "Mithraculus sculptus", "Mithracidae", "Caraïbes", "sea", "crab", True, 60, "Mange les algues bulles."),
    ("Crabe porcelaine", "Neopetrolisthes maculatus", "Porcellanidae", "Indo-Pacifique", "sea", "crab", True, 60, "Vit dans une anémone."),
    ("Turbo", "Turbo fluctuosus", "Turbinidae", "Pacifique Est", "sea", "snail", True, 40, "Brouteur d'algues."),
    ("Trochus", "Trochus histrio", "Trochidae", "Indo-Pacifique", "sea", "snail", True, 40, "Brouteur d'algues, se retourne seul."),
    ("Astraea", "Lithopoma tectum", "Turbinidae", "Caraïbes", "sea", "snail", True, 40, "Brouteur d'algues."),
    ("Nassarius", "Nassarius vibex", "Nassariidae", "Atlantique Ouest", "sea", "snail", True, 40, "Nettoie le sable."),
    ("Cérithe", "Cerithium sp.", "Cerithiidae", "Indo-Pacifique", "sea", "snail", True, 40, "Nettoie le sable et les vitres."),
    ("Bénitier crocea", "Tridacna crocea", "Cardiidae", "Indo-Pacifique", "sea", "clam", True, 200, "Forte lumière ; se fixe sur la roche."),
    ("Bénitier maxima", "Tridacna maxima", "Cardiidae", "Indo-Pacifique", "sea", "clam", True, 300, "Forte lumière."),
    ("Bénitier squamosa", "Tridacna squamosa", "Cardiidae", "Indo-Pacifique", "sea", "clam", True, 300, "Lumière moyenne à forte, sur le sable."),
    ("Oursin boule", "Mespilia globulus", "Toxopneustidae", "Indo-Pacifique", "sea", "urchin", True, 100, "Brouteur, peut déplacer les boutures."),
    ("Étoile de mer des sables", "Archaster typicus", "Archasteridae", "Indo-Pacifique", "sea", "starfish", True, 200, "Besoin d'un grand sol sableux."),
    ("Ophiure", "Ophiothrix sp.", "Ophiotrichidae", "Indo-Pacifique", "sea", "starfish", True, 100, "Nettoyeuse nocturne."),
    ("Anémone bulle", "Entacmaea quadricolor", "Actiniidae", "Indo-Pacifique", "sea", "anemone", False, 200, "Se déplace et peut piquer les coraux."),
    ("Crevette Red Cherry", "Neocaridina davidi", "Atyidae", "Taïwan", "pure", "shrimp", True, 20, "Robuste et prolifique."),
    ("Crevette Amano", "Caridina multidentata", "Atyidae", "Japon", "pure", "shrimp", True, 40, "Excellente mangeuse d'algues."),
    ("Crevette Crystal Red", "Caridina cantonensis", "Atyidae", "Chine", "pure", "shrimp", True, 30, "Exigeante : eau douce et acide."),
    ("Crevette bambou", "Atyopsis moluccensis", "Atyidae", "Asie du Sud-Est", "pure", "shrimp", True, 80, "Filtreuse, aime le courant."),
    ("Néritine zèbre", "Vittina natalensis", "Neritidae", "Afrique de l'Est", "pure", "snail", True, 20, "Mange les algues, pas de reproduction en eau douce."),
    ("Planorbe", "Planorbella duryi", "Planorbidae", "Amérique du Nord", "pure", "snail", True, 20, "Prolifère si trop de nourriture."),
    ("Ampullaire", "Pomacea diffusa", "Ampullariidae", "Amérique du Sud", "pure", "snail", True, 40, "Peut manger les plantes tendres."),
    ("Mélanoïde", "Melanoides tuberculata", "Thiaridae", "Afrique / Asie", "pure", "snail", True, 20, "Aère le sol, très prolifique."),
    ("Escargot assassin", "Anentome helena", "Nassariidae", "Asie du Sud-Est", "pure", "snail", True, 40, "Mange les autres escargots."),
    ("Écrevisse naine", "Cambarellus patzcuarensis", "Cambaridae", "Mexique", "pure", "other", True, 60, "Peut s'en prendre aux crevettes naines."),
]


def _species_rows():
    for common, scientific, family, origin, size, volume, reef_safe, notes in MARINE_FISH_SPECIES:
        yield FishSpecies, dict(
            common_name=common, scientific_name=scientific, water_type=AquariumWaterType.sea, family=family,
            origin=origin, max_height=size, min_volume=volume, reef_safe=reef_safe, notes=notes,
        )
    for common, scientific, family, origin, size, volume, notes in FRESHWATER_FISH_SPECIES:
        yield FishSpecies, dict(
            common_name=common, scientific_name=scientific, water_type=AquariumWaterType.pure, family=family,
            origin=origin, max_height=size, min_volume=volume, reef_safe=True, notes=notes,
        )
    for (common, scientific, coral_type, family, origin, light_min, light_max, brew_min, brew_max,
         aggressiveness, resistance, location, notes) in CORAL_SPECIES:
        yield CoralSpecies, dict(
            common_name=common, scientific_name=scientific, type=CoralType(coral_type), family=family,
            origin=origin, light_min=light_min, light_max=light_max, brewing_min=brew_min,
            brewing_max=brew_max, aggressiveness_level=aggressiveness, resistance_level=resistance,
            location_level=location, notes=notes,
        )
    for (common, scientific, family, origin, light_min, light_max, temp_min, temp_max, growing,
         resistance, height, location, notes) in PLANT_SPECIES:
        yield PlantSpecies, dict(
            common_name=common, scientific_name=scientific, family=family, origin=origin,
            light_min=light_min, light_max=light_max, temperature_min=temp_min, temperature_max=temp_max,
            growing=PlantGrowing(growing), resistance_level=resistance, max_height=height,
            location=PlantLocation(location), notes=notes,
        )
    for common, scientific, family, origin, water, category, reef_safe, volume, notes in INVERTEBRATE_SPECIES:
        yield InvertebrateSpecies, dict(
            common_name=common, scientific_name=scientific, family=family, origin=origin,
            water_type=AquariumWaterType(water), category=InvertebrateCategory(category),
            reef_safe=reef_safe, min_volume=volume, notes=notes,
        )


def seed_species_catalog(db: Session) -> None:
    """Ajoute les espèces du jeu de départ absentes (par nom commun, sans tenir compte
    de la casse : variétés d'une même espèce), sans toucher aux existantes."""
    known: dict[type, set[str]] = {}
    added = 0
    for model, row in _species_rows():
        if model not in known:
            known[model] = {name.strip().lower() for (name,) in db.query(model.common_name)}
        key = row["common_name"].strip().lower()
        if key in known[model]:
            continue
        db.add(model(**row, builtin=True))
        known[model].add(key)
        added += 1

    if added:
        db.commit()
        logger.info("Catalogue d'espèces : %d espèce(s) ajoutée(s)", added)
