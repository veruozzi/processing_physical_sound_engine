#!/usr/bin/env python3
"""
Generate a 3D mass-spring topology from a BioSonix-style JSON config.

Reads node positions from `node_positions_biosonix` (if present) or falls back
to a grid derived from `geometry`. Outputs a JSON file with `masses` and
`springs` arrays suitable for importing into Processing or other engines.

Usage:
  python3 generate_topology.py --config /path/to/config.json --out topology.json

The script connects nodes that lie within a distance cutoff (default: 1.6 * geometry.distance)
to form springs. Each spring contains rest_length, stiffness and damping values
inherited from `parameters` in the config.
"""
import json
# Instead of using argparse, set these script-level variables to configure
# the run. Edit them directly when you want to change inputs.
# Path to JSON config (example: '/home/ccml/biosonix/SoundModels/US/config_model.json')
CONFIG_PATH = 'config_compression_2D_data_4.json'
# Output topology JSON path
OUT_PATH = 'topology.json'
# Multiply geometry.distance by this to obtain the spring cutoff
CUTOFF_MULT = 1.6
import math
from dataclasses import dataclass, asdict
from typing import List, Tuple


@dataclass
class Mass3D:
    id: str
    x: float
    y: float
    z: float
    mass: float = 1.0
    radius: float = 1.0


@dataclass
class SpringDamper3D:
    id: str
    a: str
    b: str
    rest_length: float
    stiffness: float
    damping: float


def load_config(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


def build_masses_from_nodes(nodes: List[Tuple[float, float, float]], mass_value: float, radius: float) -> List[Mass3D]:
    # If nodes form a regular grid we will try to give them BioSonix-style names
    # like m_ix_iy_iz by computing unique sorted coordinate lists for each axis.
    masses = []
    xs = sorted({round(float(p[0]), 6) for p in nodes})
    ys = sorted({round(float(p[1]), 6) for p in nodes})
    zs = sorted({round(float(p[2]), 6) for p in nodes})

    # create lookup to indices
    x_idx = {v: i for i, v in enumerate(xs)}
    y_idx = {v: i for i, v in enumerate(ys)}
    z_idx = {v: i for i, v in enumerate(zs)}

    for i, (x, y, z) in enumerate(nodes):
        xr = round(float(x), 6)
        yr = round(float(y), 6)
        zr = round(float(z), 6)
        # default sequential id if something goes wrong
        seq_id = f"m_{i}"
        bio_id = seq_id
        try:
            ix = x_idx[xr]
            iy = y_idx[yr]
            iz = z_idx[zr]
            bio_id = f"m_{ix}_{iy}_{iz}"
        except Exception:
            bio_id = seq_id

        masses.append(Mass3D(id=bio_id, x=float(x), y=float(y), z=float(z), mass=mass_value, radius=radius))
    return masses


def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)


def build_springs(masses: List[Mass3D], cutoff: float, stiffness: float, damping: float) -> List[SpringDamper3D]:
    springs = []
    n = len(masses)
    for i in range(n):
        for j in range(i+1, n):
            p1 = (masses[i].x, masses[i].y, masses[i].z)
            p2 = (masses[j].x, masses[j].y, masses[j].z)
            d = distance(p1, p2)
            if d <= cutoff:
                springs.append(SpringDamper3D(id=f"s_{i}_{j}", a=masses[i].id, b=masses[j].id, rest_length=d, stiffness=stiffness, damping=damping))
    return springs


def parse_bio_id(bio_id: str):
    """Parse BioSonix id like m_ix_iy_iz into tuple (ix,iy,iz) or None."""
    try:
        parts = bio_id.split("_")
        if parts[0] != 'm' or len(parts) < 4:
            return None
        return (int(parts[1]), int(parts[2]), int(parts[3]))
    except Exception:
        return None


def build_springs_by_interaction(masses: List[Mass3D], interaction_types: List[str], stiffness: float, damping: float) -> List[SpringDamper3D]:
    """Build springs according to per-node interaction types.

    interaction_types: list aligned with masses, each entry one of 'FIRST','SECOND','FULLY'
    If masses ids are not parseable as grid coordinates, this function returns None
    to indicate fallback to cutoff-based connectivity should be used.
    """
    # build grid map
    grid_map = {}
    coords = [parse_bio_id(m.id) for m in masses]
    if any(c is None for c in coords):
        return None

    for idx, c in enumerate(coords):
        grid_map[c] = idx

    # define offset sets
    first_offsets = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    second_offsets = first_offsets + [
        (1,1,0),(1,-1,0),(-1,1,0),(-1,-1,0),
        (1,0,1),(1,0,-1),(-1,0,1),(-1,0,-1),
        (0,1,1),(0,1,-1),(0,-1,1),(0,-1,-1)
    ]
    fully_offsets = []
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            for dz in (-1,0,1):
                if dx == 0 and dy == 0 and dz == 0:
                    continue
                fully_offsets.append((dx,dy,dz))

    springs = []
    n = len(masses)
    for i in range(n):
        base_coord = coords[i]
        itype = (interaction_types[i] or 'FIRST').upper() if interaction_types is not None else 'FIRST'
        if itype == 'FIRST':
            offsets = first_offsets
        elif itype == 'SECOND':
            offsets = second_offsets
        elif itype == 'FULLY':
            offsets = fully_offsets
        else:
            offsets = first_offsets

        for off in offsets:
            neigh = (base_coord[0] + off[0], base_coord[1] + off[1], base_coord[2] + off[2])
            j = grid_map.get(neigh, None)
            if j is None:
                continue
            # avoid duplicates: only create when j > i
            if j > i:
                p1 = (masses[i].x, masses[i].y, masses[i].z)
                p2 = (masses[j].x, masses[j].y, masses[j].z)
                d = distance(p1, p2)
                springs.append(SpringDamper3D(id=f"s_{i}_{j}", a=masses[i].id, b=masses[j].id, rest_length=d, stiffness=stiffness, damping=damping))
    return springs


def resolve_pair_interaction(inter_i: str, inter_j: str) -> str:
    """Return the pairwise interaction name between two per-mass interaction settings.

    Uses ordering FIRST < SECOND < FULLY and returns the more permissive one.
    """
    order = {"FIRST": 1, "SECOND": 2, "FULLY": 3}
    i_v = order.get(str(inter_i).upper(), 1)
    j_v = order.get(str(inter_j).upper(), 1)
    rev = {v: k for k, v in order.items()}
    return rev[max(i_v, j_v)]


def compute_spring_params(i_idx: int, j_idx: int, masses: List[Mass3D], node_tissue_labels, per_mass_interaction, interaction_rules, default_k, default_c):
    """Compute stiffness and damping for a spring between masses i and j using interaction_rules.

    interaction_rules may contain keys:
      - 'K_by_interaction', 'C_by_interaction' : map interactionName -> value
      - 'K_by_class', 'C_by_class' : map classLabel -> value (used as mean of two classes)
      - 'K_by_class_pair', 'C_by_class_pair' : map '1-2' -> value
    """
    # defaults
    k = float(default_k)
    c = float(default_c)

    rules = interaction_rules or {}

    # determine interaction name (FIRST/SECOND/FULLY) using per_mass_interaction if available
    inter_name = None
    try:
        if per_mass_interaction is not None:
            inter_name = resolve_pair_interaction(per_mass_interaction[i_idx], per_mass_interaction[j_idx])
    except Exception:
        inter_name = None

    # try class-based labels
    li = None
    lj = None
    try:
        if node_tissue_labels is not None:
            li = str(node_tissue_labels[i_idx])
            lj = str(node_tissue_labels[j_idx])
    except Exception:
        li = lj = None

    # 1) class_pair explicit
    if li is not None and lj is not None:
        cp_key = f"{li}-{lj}"
        cp_key_rev = f"{lj}-{li}"
        k_by_pair = rules.get('K_by_class_pair', {})
        c_by_pair = rules.get('C_by_class_pair', {})
        if cp_key in k_by_pair:
            k = float(k_by_pair[cp_key])
        elif cp_key_rev in k_by_pair:
            k = float(k_by_pair[cp_key_rev])
        if cp_key in c_by_pair:
            c = float(c_by_pair[cp_key])
        elif cp_key_rev in c_by_pair:
            c = float(c_by_pair[cp_key_rev])

    # 2) interaction-level
    if inter_name is not None:
        k_by_inter = rules.get('K_by_interaction', {})
        c_by_inter = rules.get('C_by_interaction', {})
        if inter_name in k_by_inter:
            k = float(k_by_inter[inter_name])
        if inter_name in c_by_inter:
            c = float(c_by_inter[inter_name])

    # 3) per-class average
    if (('K_by_class' in rules) or ('C_by_class' in rules)) and li is not None and lj is not None:
        k_by_class = rules.get('K_by_class', {})
        c_by_class = rules.get('C_by_class', {})
        if li in k_by_class or lj in k_by_class:
            try:
                vi = float(k_by_class.get(li, k))
                vj = float(k_by_class.get(lj, k))
                k = (vi + vj) / 2.0
            except Exception:
                pass
        if li in c_by_class or lj in c_by_class:
            try:
                vi = float(c_by_class.get(li, c))
                vj = float(c_by_class.get(lj, c))
                c = (vi + vj) / 2.0
            except Exception:
                pass

    return k, c


def adjust_springs_params(springs: List[SpringDamper3D], masses: List[Mass3D], node_tissue_labels, per_mass_interaction, interaction_rules, default_k, default_c):
    """Adjust stiffness/damping of existing springs in-place using rules."""
    # build id->index map for masses
    id_to_idx = {m.id: idx for idx, m in enumerate(masses)}
    for s in springs:
        ia = id_to_idx.get(s.a)
        ib = id_to_idx.get(s.b)
        if ia is None or ib is None:
            continue
        k, c = compute_spring_params(ia, ib, masses, node_tissue_labels, per_mass_interaction, interaction_rules, default_k, default_c)
        s.stiffness = k
        s.damping = c


def build_springs_with_class_connectivity(masses: List[Mass3D], per_mass_mult: List[float], geom_distance: float, stiffness: float, damping: float) -> List[SpringDamper3D]:
    """Build springs using per-mass connectivity multipliers.

    For a pair of masses i,j the cutoff used is max(per_mass_mult[i], per_mass_mult[j]) * geom_distance.
    This lets different tissue classes have different effective interaction radii.
    """
    springs = []
    n = len(masses)
    for i in range(n):
        for j in range(i+1, n):
            p1 = (masses[i].x, masses[i].y, masses[i].z)
            p2 = (masses[j].x, masses[j].y, masses[j].z)
            d = distance(p1, p2)
            cutoff = max(per_mass_mult[i], per_mass_mult[j]) * float(geom_distance)
            if d <= cutoff:
                springs.append(SpringDamper3D(id=f"s_{i}_{j}", a=masses[i].id, b=masses[j].id, rest_length=d, stiffness=stiffness, damping=damping))
    return springs


def write_topology(out_path: str, masses: List[Mass3D], springs: List[SpringDamper3D]):
    out = {
        "masses": [asdict(m) for m in masses],
        "springs": [asdict(s) for s in springs]
    }
    # If the original config contained sonification setup, include it verbatim
    try:
        # cfg is available in outer scope when called from main; if not, skip
        if 'sonification_set_up' in globals().get('cfg', {}):
            out['sonification_set_up'] = globals()['cfg'].get('sonification_set_up')
    except Exception:
        pass
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)


def main():
    # Use script-level constants instead of argparse
    cfg = load_config(CONFIG_PATH)

    # Prefer explicit nodes if available
    nodes = cfg.get('sonification_set_up', {}).get('node_positions_biosonix')

    if nodes and len(nodes) > 0:
        node_positions = [(float(x), float(y), float(z)) for x, y, z in nodes]
    else:
        # Try to build grid from geometry
        geom = cfg.get('geometry', {})
        dx = geom.get('dx', 1)
        dy = geom.get('dy', 1)
        dz = geom.get('dz', 1)
        distance_val = geom.get('distance', 10.0)
        # simple regular grid centered at origin
        node_positions = []
        for ix in range(int(max(1, dx))):
            for iy in range(int(max(1, dy))):
                for iz in range(int(max(1, dz))):
                    x = (ix - dx/2) * distance_val
                    y = (iy - dy/2) * distance_val
                    z = (iz - dz/2) * distance_val
                    node_positions.append((x, y, z))

    # Parameters: K -> stiffness, M -> mass, C -> damping. Use first element as default.
    params = cfg.get('parameters', {})
    K = params.get('K', [1.0])
    M = params.get('M', [1.0])
    C = params.get('C', [0.01])
    stiffness = float(K[0]) if isinstance(K, list) and len(K) > 0 else float(K)
    mass_value = float(M[0]) if isinstance(M, list) and len(M) > 0 else float(M)
    damping = float(C[0]) if isinstance(C, list) and len(C) > 0 else float(C)

    # geometry distance used to choose cutoff
    geom_distance = cfg.get('geometry', {}).get('distance', 10.0)
    cutoff = CUTOFF_MULT * float(geom_distance)

    print(f"Loaded {len(node_positions)} node positions from config")
    # initial radius (will be possibly overridden per-node below)
    initial_radius = cfg.get('parameters', {}).get('massesRadius', cfg.get('parameters', {}).get('masses_radius', cfg.get('geometry', {}).get('massesRadius', 1.0)))
    # if it's a list, use first element as temporary default
    if isinstance(initial_radius, list) and len(initial_radius) > 0:
        initial_radius_val = float(initial_radius[0])
    else:
        try:
            initial_radius_val = float(initial_radius)
        except Exception:
            initial_radius_val = 1.0

    masses = build_masses_from_nodes(node_positions, mass_value=mass_value, radius=initial_radius_val)

    # Assign per-mass radius if node_tissue_labels and massesRadius per-class are provided
    node_tissue_labels = cfg.get('sonification_set_up', {}).get('node_tissue_labels')
    masses_radius_cfg = cfg.get('parameters', {}).get('massesRadius', cfg.get('parameters', {}).get('masses_radius', None))
    if node_tissue_labels and masses_radius_cfg is not None:
        # If masses_radius_cfg is a list, map class label -> radius
        if isinstance(masses_radius_cfg, list):
            for i, m in enumerate(masses):
                try:
                    lbl = node_tissue_labels[i]
                    # assume 1-based integer labels commonly used in configs
                    idx = int(lbl) - 1 if (isinstance(lbl, (int, float)) or (isinstance(lbl, str) and lbl.isdigit())) else int(lbl)
                    if 0 <= idx < len(masses_radius_cfg):
                        m.radius = float(masses_radius_cfg[idx])
                    else:
                        m.radius = float(masses_radius_cfg[0])
                except Exception:
                    m.radius = float(masses_radius_cfg[0])
        else:
            # scalar
            try:
                rv = float(masses_radius_cfg)
            except Exception:
                rv = initial_radius_val
            for m in masses:
                m.radius = rv

    # Optional: class-based connectivity
    # node_classes: list aligned with node_positions / masses, giving a class label per node
    node_classes = cfg.get('sonification_set_up', {}).get('node_classes') or cfg.get('node_classes')
    # class_cutoffs: mapping class_label -> multiplier (float). Multiplier is applied to geometry.distance
    class_cutoffs = (cfg.get('sonification_set_up', {}).get('class_cutoffs')
                     or cfg.get('class_cutoffs')
                     or cfg.get('interaction_rules', {}).get('class_cutoffs', None))

    if node_classes and class_cutoffs:
        # Build per-mass multipliers list (default to global CUTOFF_MULT)
        per_mass_mult = []
        for i, m in enumerate(masses):
            try:
                label = node_classes[i]
            except Exception:
                label = None
            mult = class_cutoffs.get(str(label), class_cutoffs.get(label, None)) if label is not None else None
            if mult is None:
                mult = CUTOFF_MULT
            per_mass_mult.append(float(mult))

        springs = build_springs_with_class_connectivity(masses, per_mass_mult=per_mass_mult, geom_distance=geom_distance, stiffness=stiffness, damping=damping)
        # diagnostic summary: counts per class
        class_counts = {}
        for lbl in node_classes:
            class_counts[lbl] = class_counts.get(lbl, 0) + 1
        print(f"Class counts: {class_counts}")
        # allow interaction_rules to override per-spring stiffness/damping
        interaction_rules = cfg.get('interaction_rules', {})
        if interaction_rules:
            adjust_springs_params(springs, masses, node_tissue_labels, None, interaction_rules, stiffness, damping)
        print(f"Created {len(masses)} masses and {len(springs)} springs (class-based connectivity)")
    else:
        # Try to use interactionType from geometry (can be single string or list per-class)
        geom_interaction = cfg.get('geometry', {}).get('interactionType', cfg.get('geometry', {}).get('interaction_type', None))
        per_mass_interaction = None
        if geom_interaction is not None:
            if isinstance(geom_interaction, list) and node_tissue_labels:
                # map per-node by tissue label
                per_mass_interaction = []
                for i, m in enumerate(masses):
                    try:
                        lbl = node_tissue_labels[i]
                        idx = int(lbl) - 1 if (isinstance(lbl, (int, float)) or (isinstance(lbl, str) and str(lbl).isdigit())) else int(lbl)
                        if 0 <= idx < len(geom_interaction):
                            per_mass_interaction.append(str(geom_interaction[idx]))
                        else:
                            per_mass_interaction.append(str(geom_interaction[0]))
                    except Exception:
                        per_mass_interaction.append(str(geom_interaction[0]))
            elif isinstance(geom_interaction, str):
                per_mass_interaction = [geom_interaction] * len(masses)

        springs = None
        if per_mass_interaction is not None:
            springs = build_springs_by_interaction(masses, per_mass_interaction, stiffness=stiffness, damping=damping)
            # allow interaction_rules to override per-spring stiffness/damping
            interaction_rules = cfg.get('interaction_rules', {})
            if interaction_rules:
                adjust_springs_params(springs, masses, node_tissue_labels, per_mass_interaction, interaction_rules, stiffness, damping)

        if springs is None:
            springs = build_springs(masses, cutoff=cutoff, stiffness=stiffness, damping=damping)
            print(f"Created {len(masses)} masses and {len(springs)} springs (cutoff={cutoff})")
        else:
            print(f"Created {len(masses)} masses and {len(springs)} springs (interaction-based connectivity)")
    # expose cfg to write_topology so sonification_set_up can be copied
    globals()['cfg'] = cfg
    write_topology(OUT_PATH, masses, springs)
    print(f"Topology written to {OUT_PATH}")


if __name__ == '__main__':
    main()
