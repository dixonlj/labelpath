"""Create a toy persistent Relate store and read it back. Placeholders only; not medical data."""
from pathlib import Path
import relate

STORE = Path(__file__).resolve().parents[1] / "data" / "labelpath.rl"
STORE.parent.mkdir(parents=True, exist_ok=True)
params = {
    "a": "toy-drug-a", "a_name": "Toy Drug A",
    "b": "toy-drug-b", "b_name": "Toy Drug B",
    "c": "toy-drug-c", "c_name": "Toy Drug C",
    "kind": "interactions",
    "text": "Placeholder text only: toy-drug-a mentions toy-drug-b.",
    "summary": "toy placeholder interaction",
}

with relate.connect(str(STORE)) as conn:
    conn.execute(
        """
        CREATE (a:Drug {key: $a, generic_name: $a_name}),
               (b:Drug {key: $b, generic_name: $b_name}),
               (c:Drug {key: $c, generic_name: $c_name}),
               (s:Section {kind: $kind, text: $text}),
               (a)-[:LABELED_INTERACTION {summary: $summary}]->(b),
               (a)-[:HAS_SECTION]->(s)
        """,
        params,
    )

print("wrote", STORE, "exists=", STORE.is_file())
reader = relate.connect(str(STORE), read_only=True)
print("drugs:", reader.execute("MATCH (d:Drug) RETURN d.key AS key ORDER BY d.key").fetchall())
print("interaction:", reader.execute("MATCH (a:Drug)-[r:LABELED_INTERACTION]->(b:Drug) RETURN a.key AS from_key, b.key AS to_key, r.summary AS summary").single())
print("section:", reader.execute("MATCH (d:Drug)-[:HAS_SECTION]->(s:Section) RETURN d.key AS drug_key, s.kind AS kind, s.text AS text").single())
print("nodes:", reader.execute("MATCH (n) RETURN count(n) AS n").single()["n"])
reader.close()
