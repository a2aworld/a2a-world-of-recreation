import math
from typing import Optional
from ipfs_client import IPFSClient

class ArtifactMinter:
    """Generates geometric SVGs representing 'Artifacts of Alliance' and pins them to IPFS."""

    @staticmethod
    def generate_mandala_svg(agent1: str, agent2: str, lat: float, lon: float, decrypted_text: str) -> bytes:
        """Dynamically builds an SVG based on coordinates and agents."""
        
        # Base math for geometric shapes
        radius = 150
        cx = 250
        cy = 250
        
        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500" width="500" height="500">',
            f'<rect width="500" height="500" fill="#0f172a" />',
            # Outer Ring
            f'<circle cx="{cx}" cy="{cy}" r="{radius+20}" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0.5"/>',
            # Inner polygon based on coordinate math
            f'<polygon points="'
        ]
        
        # Determine number of sides based on latitude (abs) to make it unique per coordinate
        sides = max(3, int(abs(lat) % 10) + 3)
        points = []
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            px = cx + radius * math.cos(angle)
            py = cy + radius * math.sin(angle)
            points.append(f"{px},{py}")
            
        svg.append(" ".join(points) + f'" fill="none" stroke="#818cf8" stroke-width="3" />')
        
        # Connecting lines (Sacred geometry feel)
        for p1 in points:
            for p2 in points:
                if p1 != p2:
                    svg.append(f'<line x1="{p1.split(",")[0]}" y1="{p1.split(",")[1]}" x2="{p2.split(",")[0]}" y2="{p2.split(",")[1]}" stroke="#4f46e5" stroke-width="1" opacity="0.3"/>')

        # Text Elements
        svg.append(f'<text x="{cx}" y="40" font-family="monospace" font-size="16" fill="#e2e8f0" text-anchor="middle">ARTIFACT OF ALLIANCE</text>')
        svg.append(f'<text x="{cx}" y="65" font-family="monospace" font-size="12" fill="#94a3b8" text-anchor="middle">LOC: {lat}, {lon}</text>')
        
        svg.append(f'<text x="{cx}" y="{cy-10}" font-family="monospace" font-size="14" fill="#38bdf8" text-anchor="middle">{agent1}</text>')
        svg.append(f'<text x="{cx}" y="{cy+15}" font-family="monospace" font-size="14" fill="#818cf8" text-anchor="middle">×</text>')
        svg.append(f'<text x="{cx}" y="{cy+40}" font-family="monospace" font-size="14" fill="#38bdf8" text-anchor="middle">{agent2}</text>')

        # Decrypted Fragment at bottom
        svg.append(f'<text x="{cx}" y="450" font-family="serif" font-style="italic" font-size="12" fill="#cbd5e1" text-anchor="middle">"{decrypted_text}"</text>')
        
        svg.append('</svg>')
        
        return "\n".join(svg).encode('utf-8')

    @classmethod
    async def mint_alliance_artifact(cls, agent1_name: str, agent2_name: str, lat: float, lon: float, decrypted_text: str) -> Optional[str]:
        """Generate SVG and pin it to IPFS."""
        svg_bytes = cls.generate_mandala_svg(agent1_name, agent2_name, lat, lon, decrypted_text)
        filename = f"alliance_{lat}_{lon}.svg"
        
        ipfs_url = await IPFSClient.pin_file(svg_bytes, filename, "image/svg+xml")
        return ipfs_url
