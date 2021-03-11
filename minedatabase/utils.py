"""Utils.py: contains basic functions reused in various contexts in other
modules"""
import collections
import csv
import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from itertools import chain, islice
from os import path
from typing import Callable, Generator, List, Tuple, Union

import pymongo
import rdkit
from rdkit.Chem import AllChem


StoichTuple = collections.namedtuple("StoichTuple", "stoich,c_id")


class Chunks(Iterator):
    """A class to chunk an iterator up into defined sizes."""

    def __init__(self, it: Iterable, chunk_size: int = 1, return_list: bool = False):
        self._it = iter(it)
        self._chunk_size = chunk_size
        self._return_list = return_list

    def __iter__(self) -> Iterator:
        return self

    def __next__(self):
        return self.next()

    def next(self):
        """Returns the next chunk from the iterable.
        This method is not thread-safe.
        """

        def peek(iterable):
            """peek at first element of iterable to determine if it is empty."""
            try:
                first = next(iterable)
            except StopIteration:
                return None
            return chain([first], iterable)

        next_slice = islice(self._it, self._chunk_size)
        next_slice = peek(next_slice)

        if next_slice:
            if self._return_list:
                return list(next_slice)
            else:
                return next_slice
        else:
            raise StopIteration


def file_to_dict_list(filepath: str) -> list:
    """Accept a path to a CSV, TSV or JSON file and return a dictionary list.

    Parameters
    ----------
    filepath : str
        File to load into a dictionary list.

    Returns
    -------
    list
        Dictionary list.
    """
    if ".tsv" in filepath:
        reader = csv.DictReader(open(filepath), dialect="excel-tab")
    elif ".csv" in filepath:
        reader = csv.DictReader(open(filepath))
    elif ".json" in filepath:
        reader = json.load(open(filepath))
    else:
        raise ValueError("Unrecognized input file type")
    return list(reader)


def get_fp(smi: str) -> AllChem.RDKFingerprint:
    """Generate default RDKFingerprint.

    Parameters
    ----------
    smi : str
        SMILES of the molecule.

    Returns
    -------
    AllChem.RDKFingerprint
        Default fingerprint of the molecule.
    """
    mol = AllChem.MolFromSmiles(smi)
    fp = AllChem.RDKFingerprint(mol)
    return fp


def compound_hash(
    smi: str, cpd_type: str = "Predicted", inchi_blocks: int = 1
) -> Tuple[str, Union[str, None]]:
    """Create a hash string for a given compound.

    This function generates an unique identifier for a compound, ensuring a
    normalized SMILES. The compound hash is generated by sanitizing and neutralizing the
    SMILES and then generating a hash from the sha1 method in the haslib.

    The hash is prepended with a character depending on the type. Default value is "C":
        1. Coreactant: "X"
        2. Target Compound: "T"
        3. Predicted Compound: "C"

    Parameters
    ----------
    smi : str
        The SMILES of the compound.
    cpd_type : str, optional
        The Compound Type, by default 'Predicted'.

    Returns
    -------
    Tuple[str, Union[str, None]]
        Compound hash, InChI-Key.
    """

    # The ID is generated from a hash of either the InChI key (partial) or SMILES
    # The InChI key is used if the SMILES does not contain '*'
    inchi_key = None

    if "*" not in smi:
        compound = AllChem.MolFromSmiles(smi)
        inchi_key = AllChem.MolToInchiKey(compound)
        # Take the first part of the InChIKey as it contains structural
        # information only
        compound = inchi_key.rsplit("-", 3 - inchi_blocks)[0]
    else:
        compound = smi

    # Create standard length hash string using hashlib module
    chash = hashlib.sha1(compound.encode("utf-8")).hexdigest()

    # Mark cofactors with an X at the beginning, targets with a T, all else with a C
    if cpd_type == "Coreactant":
        return "X" + chash, compound
    elif cpd_type == "Target Compound":
        return "T" + chash, inchi_key
    else:
        return "C" + chash, inchi_key


def convert_sets_to_lists(obj: dict) -> dict:
    """Recursively converts dictionaries that contain sets to lists.

    Parameters
    ----------
    obj : dict
        Input object to convert sets from.

    Returns
    -------
    dict
        dictionary with no sets.
    """
    if isinstance(obj, set):
        # This brings short names to the top of the list
        try:
            obj = sorted(list(obj), key=len)
        except TypeError:
            obj = list(obj)
    elif isinstance(obj, dict):
        for key in obj:
            obj[key] = convert_sets_to_lists(obj[key])
    return obj


def get_dotted_field(input_dict: dict, accessor_string: str) -> dict:
    """Gets data from a dictionary using a dotted accessor-string.

    Parameters
    ----------
    input_dict : dict
        A nested dictionary.
    accessor_string : str
        The value in the nested dict.

    Returns
    -------
    dict
        Data from the dictionary.
    """
    current_data = input_dict
    for chunk in accessor_string.split("."):
        current_data = current_data.get(chunk, {})
    return current_data


def save_dotted_field(accessor_string: str, data: dict):
    """Saves data to a dictionary using a dotted accessor-string.

    Parameters
    ----------
    accessor_string : str
        A dotted path description, e.g. "DBLinks.KEGG".
    data : dict
        The value to be stored.

    Returns
    -------
    dict
        The nested dictionary.
    """
    for chunk in accessor_string.split(".")[::-1]:
        data = {chunk: data}
    return data


def memoize(func: Callable):
    """Memoization decorator for a function taking one or more arguments.

    Parameters
    ----------
    func : Callable
        Function to memoize.
    """

    class MemoDict(dict):
        """Class to store outputs for previous inputs. If not previously input
        into func, gets added to the dict."""

        def __getitem__(self, *key):
            return dict.__getitem__(self, key)

        def __missing__(self, key):
            ret = self[key] = func(*key)
            return ret

    return MemoDict().__getitem__


def prevent_overwrite(write_path: str) -> str:
    """Prevents overwrite of existing output files by appending "_new" when
    needed.

    Parameters
    ----------
    write_path : str
        Path to write.

    Returns
    -------
    str
        Updated path to write.
    """
    while path.exists(write_path):
        split = write_path.split(".")
        # Make sure that files without an extension are still valid (otherwise,
        # split would create a list of one string which would give an index
        # error when sp[-2] is called)
        if len(split) > 1:
            split[-2] += "_new"
            write_path = ".".join(split)
        else:
            write_path += "_new"
    return write_path


def approximate_matches(list1: list, list2: list, epsilon: float = 0.01) -> Generator:
    """Searches for matches between two lists.

    Takes two list of tuples and searches for matches of tuples first value
    within the supplied epsilon. Emits tuples with the tuples second values
    where found. if a value in one dist does not match the other list, it is
    emitted alone.

    Parameters
    ----------
    list1 : list
        First list of tuples.
    list2 : list
        Second list of tuples.
    epsilon : float, optional
        Maximum difference in, by default 0.01.

    Yields
    -------
    Generator
        Generator that yields matches.
    """
    list1.sort()
    list2.sort()
    list1_index = 0
    list2_index = 0

    while list1_index < len(list1) or list2_index < len(list2):
        if list1_index == len(list1):
            yield (0, list2[list2_index][1])
            list2_index += 1
            continue
        if list2_index == len(list2):
            yield (list1[list1_index][1], 0)
            list1_index += 1
            continue

        list1_element = list1[list1_index][0]
        list2_element = list2[list2_index][0]

        difference = abs(list1_element - list2_element)

        if difference < epsilon:
            yield (list1[list1_index][1], list2[list2_index][1])
            list1_index += 1
            list2_index += 1
        elif list1_element < list2_element:
            yield (list1[list1_index][1], 0)
            list1_index += 1
        elif list2_element < list1_element:
            yield (0, list2[list2_index][1])
            list2_index += 1
        else:
            raise AssertionError("Unexpected else taken")


def dict_merge(finaldict: dict, sourcedict: dict) -> None:
    """Merges two dictionaries using sets to avoid duplication of values.

    Parameters
    ----------
    finaldict : dict
        Dict to merge into.
    sourcedict : dict
        Dict to merge from.
    """
    for key, val in sourcedict.items():
        if (key in finaldict) and isinstance(finaldict[key], list):
            finaldict[key] = set(finaldict[key])
        if isinstance(val, list):
            if key in finaldict:
                finaldict[key].update(val)
            else:
                finaldict[key] = set(val)
        elif isinstance(val, str):
            if key in finaldict:
                finaldict[key].update(val)
            else:
                finaldict[key] = set(val)
                finaldict[key].update(val)
        elif isinstance(val, float):
            if key not in finaldict:
                finaldict[key] = val
        elif isinstance(val, dict):
            if key not in finaldict:
                finaldict[key] = {}
            dict_merge(finaldict[key], val)


def rxn2hash(reactants: List[StoichTuple], products: List[StoichTuple]) -> str:
    """Hashes reactant and product lists.

    Generates a unique ID for a given reaction for use in MongoDB.

    Parameters
    ----------
    reactants : List[StoichTuple]
        List of reactants.
    products : List[StoichTuple]
        List of products.

    Returns
    -------
    str
        Reaction hash.
    """
    # Get text reaction to be hashed
    # this is a combination of two functions
    def to_str(half_rxn):
        return [
            f"({x[0]}) {x[1]})"
            if (len(x) == 2 and not isinstance(x, str))
            else f"(1) {x}"
            for x in sorted(half_rxn)
        ]

    def get_smiles(cpds):
        cpd_tups = [
            (stoich, cpd_dict["_id"], cpd_dict["SMILES"]) for stoich, cpd_dict in cpds
        ]
        cpd_tups.sort(key=lambda x: x[1])
        smiles = []
        for cpd in cpd_tups:
            smiles.append(f"({cpd[0]}) {cpd[2]}")
        return " + ".join(smiles)

    reactant_ids = [reactant[1]["_id"] for reactant in reactants]
    product_ids = [product[1]["_id"] for product in products]
    reactant_ids.sort()
    product_ids.sort()
    text_ids_rxn = (
        " + ".join(to_str(reactant_ids)) + " => " + " + ".join(to_str(product_ids))
    )
    # Hash text reaction
    rhash = "R" + hashlib.sha256(text_ids_rxn.encode()).hexdigest()

    # smiles
    reactant_smiles = get_smiles(reactants)
    product_smiles = get_smiles(products)

    text_smiles_rxn = reactant_smiles + " => " + product_smiles

    return rhash, text_smiles_rxn


_REACTIONS = None


def neutralise_charges(
    mol: rdkit.Chem.rdchem.Mol, reactions=None
) -> rdkit.Chem.rdchem.Mol:
    """Neutralize all charges in an rdkit mol.

    Parameters
    ----------
    mol : rdkit.Chem.rdchem.Mol
        Molecule to neutralize.
    reactions : list, optional
        patterns to neutralize, by default None.

    Returns
    -------
    rdkit.Chem.rdchem.Mol
        Neutralized molecule.
    """

    def _initialise_neutralisation_reactions():
        patts = (
            # Imidazoles
            ("[n+;H]", "n"),
            # Amines
            ("[N+;!H0]", "N"),
            # Carboxylic acids and alcohols
            ("[$([O-]);!$([O-][#7])]", "O"),
            # Thiols
            ("[S-;X1]", "S"),
            # Sulfonamides
            ("[$([N-;X2]S(=O)=O)]", "N"),
            # Enamines
            ("[$([N-;X2][C,N]=C)]", "N"),
            # Tetrazoles
            ("[n-]", "[nH]"),
            # Sulfoxides
            ("[$([S-]=O)]", "S"),
            # Amides
            ("[$([N-]C=O)]", "N"),
        )
        return [
            (AllChem.MolFromSmarts(x), AllChem.MolFromSmiles(y, False))
            for x, y in patts
        ]

    global _REACTIONS  # pylint: disable=global-statement
    if reactions is None:
        if _REACTIONS is None:
            _REACTIONS = _initialise_neutralisation_reactions()
        reactions = _REACTIONS
    for (reactant, product) in reactions:
        while mol.HasSubstructMatch(reactant):
            rms = AllChem.ReplaceSubstructs(mol, reactant, product)
            mol = rms[0]
    return mol


def score_compounds(
    db: pymongo.database,
    compounds: list,
    model_id: str,
    parent_frac: float = 0.75,
    reaction_frac: float = 0.25,
) -> List[dict]:
    """This function validates compounds against a metabolic model, returning
    only the compounds which pass.

    Parameters
    ----------
    db : Mongo DB
        Should contain a "models" collection with compound and reaction IDs
        listed.
    compounds : list
        Each element is a dict describing that compound. Should have an '_id'
        field.
    model_id : str
        KEGG organism code (e.g. 'hsa').
    parent_frac : float, optional (default: 0.75)
        Weighting for compounds derived from compounds in the provided model.
    reaction_frac : float, optional (default: 0.25)
        Weighting for compounds derived from known compounds not in the model.

    Returns
    -------
    compounds : list
        Modified version of input compounds list, where each compound now has
        a 'Likelihood_score' key and value between 0 and 1.
    """
    if not model_id:
        return compounds
    model = db.models.find_one({"_id": model_id})
    if not model:
        return compounds
    parents = set(model["Compounds"])

    for comp in compounds:
        try:
            if set(comp["DB_links"]["KEGG"]) & parents:
                comp["Likelihood_score"] = parent_frac + reaction_frac
                continue
        except KeyError:
            pass  # no worries if no KEGG id for this comp, just continue on

        if comp["Generation"] == 0:
            comp["Likelihood_score"] = reaction_frac
            continue

        comp["Likelihood_score"] = 0.0
        for source in comp["Sources"]:
            likelihood_score = reaction_frac

            try:
                for s_comp in source["Compounds"]:
                    if "DB_links" in s_comp and "KEGG" in s_comp["DB_links"]:
                        if set(s_comp["DB_links"]["KEGG"]) & parents:
                            likelihood_score += parent_frac
            except KeyError:
                s_comp = source["Compound"]  # needed for legacy MINEs
                if "DB_links" in s_comp and "KEGG" in s_comp["DB_links"]:
                    if set(s_comp["DB_links"]["KEGG"]) & parents:
                        likelihood_score += parent_frac

            if likelihood_score > comp["Likelihood_score"]:
                comp["Likelihood_score"] = likelihood_score

    return compounds


def get_smiles_from_mol_string(mol_string: str) -> str:
    """Convert a molfile in string format to a SMILES string.

    Parameters
    ----------
    mol_string : str
        molfile in string format.

    Returns
    -------
    str
        SMILES string.
    """
    mol = AllChem.MolFromMolBlock(mol_string)
    smiles = AllChem.MolToSmiles(mol)

    return smiles


def _getatom_count(mol, radical_check=False):
    """Takes a set of mol objects and returns a counter with each element
    type in the set"""
    atoms = collections.Counter()
    # Find all strings of the form A# in the molecular formula where A
    # is the element (e.g. C) and # is the number of atoms of that
    # element in the molecule. Pair is of form [A, #]
    for pair in re.findall(r"([A-Z][a-z]*)(\d*)", AllChem.CalcMolFormula(mol)):
        # Add # to atom count, unless there is no # (in which case
        # there is just one of that element, as ones are implicit in
        # chemical formulas)
        if pair[1]:
            atoms[pair[0]] += int(pair[1])
        else:
            atoms[pair[0]] += 1
    if radical_check:
        radical = any([atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()])
        if radical:
            atoms["*"] += 1
    return atoms


# def _racemization(compound, max_centers=3, carbon_only=True):
#     """Enumerates all possible stereoisomers for unassigned chiral centers.

#     :param compound: A compound
#     :type compound: rdMol object
#     :param max_centers: The maximum number of unspecified stereocenters to
#         enumerate. Sterioisomers grow 2^n_centers so this cutoff prevents lag
#     :type max_centers: int
#     :param carbon_only: Only enumerate unspecified carbon centers. (other
#         centers are often not tautomeric artifacts)
#     :type carbon_only: bool
#     :return: list of stereoisomers
#     :rtype: list of rdMol objects
#     """
#     new_comps = []
#     # FindMolChiralCenters (rdkit) finds all chiral centers. We get all
#     # unassigned centers (represented by '?' in the second element
#     # of the function's return parameters).
#     unassigned_centers = [c[0] for c in AllChem.FindMolChiralCenters(
#         compound, includeUnassigned=True) if c[1] == '?']
#     # Get only unassigned centers that are carbon (atomic number of 6) if
#     # indicated
#     if carbon_only:
#         unassigned_centers = list(
#             filter(lambda x: compound.GetAtomWithIdx(x).GetAtomicNum() == 6,
#                 unassigned_centers))
#     # Return original compound if no unassigned centers exist (or if above
#     # max specified (to prevent lag))
#     if not unassigned_centers or len(unassigned_centers) > max_centers:
#         return [compound]
#     for seq in itertools.product([1, 0], repeat=len(unassigned_centers)):
#         for atomid, clockwise in zip(unassigned_centers, seq):
#             # Get both cw and ccw chiral centers for each center. Used
#             # itertools.product to get all combinations.
#             if clockwise:
#                 compound.GetAtomWithIdx(atomid).SetChiralTag(
#                     AllChem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW)
#             else:
#                 compound.GetAtomWithIdx(atomid).SetChiralTag(
#                     AllChem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW)
#         # Duplicate C++ object so that we don't get multiple pointers to
#         # same object
#         new_comps.append(deepcopy(compound))
#     return new_comps
