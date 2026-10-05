import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import java.util.Locale;
import java.util.TreeMap;

import org.jacoco.core.analysis.Analyzer;
import org.jacoco.core.analysis.CoverageBuilder;
import org.jacoco.core.analysis.IClassCoverage;
import org.jacoco.core.analysis.ICounter;
import org.jacoco.core.tools.ExecFileLoader;

/**
 * Coverage report in the layout of the EclEmma Coverage view: workspace > project > source folder > package >
 * file, with Coverage, Covered Instructions, Missed Instructions and Total Instructions. Reads one or more .exec
 * files and analyzes, for every Maven module of the workspace (only com.ccp, com.jn, com.jb and com.vis
 * classes), the bytecode that actually ran: the module's jar in the local Maven repository (what the tests JVM
 * loads), an explicit override (the API runs from a snapshot of its target/classes), or target/classes as the
 * last resort. JaCoCo matches classes by a checksum of the bytecode, and Eclipse rewrites target/classes with
 * its own compiler (without the AspectJ weaving) whenever it builds, so target/classes silently stopped
 * matching in the middle of a run on 2026-10-02 and 3/4 of the code vanished from the report. Classes that
 * still do not match are counted and reported instead of dropped in silence.
 * Writes a collapsible HTML page, a TSV with one line per file and prints the tree down to the source folder level.
 *
 * usage: CoverageReport <jacoco.exec[;other.exec...]> <workspace> <output.html> <output.tsv> [subtitle] [m2 repository]
 *        [module=classesDirOrJar;...] [excludedModule;...] [tests run summary]
 */
public class CoverageReport {

	static class Node {
		final String name;
		long covered, missed;
		final TreeMap<String, Node> children = new TreeMap<>();
		Node(String name) { this.name = name; }
		Node child(String childName) { return children.computeIfAbsent(childName, Node::new); }
		long total() { return covered + missed; }
	}

	public static void main(String[] args) throws Exception {
		ExecFileLoader loader = new ExecFileLoader();
		// several .exec files (tests JVM + API) separated by ';' are merged: a probe hit in any of them counts
		for (String exec : args[0].split(";")) {
			if (!exec.isBlank()) loader.load(new File(exec));
		}
		File workspace = new File(args[1]);
		String subtitle = args.length > 4 ? args[4] : "JaCoCo instruction counters.";
		File m2 = args.length > 5 && !args[5].isBlank() ? new File(args[5]) : null;
		Map<String, File> overrides = new HashMap<>();
		if (args.length > 6) {
			for (String pair : args[6].split(";")) {
				int equals = pair.indexOf('=');
				if (equals > 0) overrides.put(pair.substring(0, equals), new File(pair.substring(equals + 1)));
			}
		}
		// modules left out of the report, such as the tests module, whose src/main is support code for the tests
		List<String> excluded = args.length > 7 ? Arrays.asList(args[7].split(";")) : new ArrayList<>();
		Map<String, File> jarsByName = m2 == null ? new HashMap<>() : findSnapshotJars(new File(m2, "com"));
		Node root = new Node("workspace");
		File[] modules = workspace.listFiles(f -> f.isDirectory() && new File(f, "pom.xml").exists());
		Arrays.sort(modules);
		long notMatched = 0;
		for (File module : modules) {
			if (excluded.contains(module.getName())) continue;
			File classes = overrides.get(module.getName());
			if (classes == null) classes = jarsByName.get(module.getName());
			if (classes == null) classes = new File(module, "target/classes");
			if (!classes.exists()) continue;
			System.out.println("analyzing " + module.getName() + " <- " + classes);
			CoverageBuilder builder = new CoverageBuilder();
			Analyzer analyzer = new Analyzer(loader.getExecutionDataStore(), builder);
			analyzeOwnClasses(analyzer, classes);
			Node project = new Node(module.getName());
			Node sourceFolder = project.child("src/main/java");
			for (IClassCoverage c : builder.getClasses()) {
				String pkg = c.getPackageName().replace('/', '.');
				boolean ownPackage = pkg.startsWith("com.ccp") || pkg.startsWith("com.jn") || pkg.startsWith("com.jb") || pkg.startsWith("com.vis");
				if (!ownPackage) continue;
				String file = c.getSourceFileName() == null ? c.getName().substring(c.getName().lastIndexOf('/') + 1) + ".class" : c.getSourceFileName();
				// a Spring Boot jar carries its dependencies (ccp_commons and the like) in BOOT-INF/lib, and the
				// analyzer opens nested jars: only the classes whose source lives in this module count here
				boolean sourceOfThisModule = new File(module, "src/main/java/" + c.getPackageName() + "/" + file).isFile();
				if (!sourceOfThisModule) continue;
				// the class ran, but from different bytecode than the one analyzed: its numbers would be wrong
				if (c.isNoMatch()) { notMatched++; continue; }
				ICounter instructions = c.getInstructionCounter();
				Node fileNode = sourceFolder.child(pkg).child(file);
				fileNode.covered += instructions.getCoveredCount();
				fileNode.missed += instructions.getMissedCount();
			}
			sum(project);
			if (project.total() > 0) root.children.put(project.name, project);
		}
		sum(root);
		if (notMatched > 0) {
			System.out.println("WARNING: " + notMatched + " classes ran from bytecode different from the analyzed one and were left out (rebuilt by Eclipse or not installed?)");
		}
		// how many tests produced these numbers: the user wants it next to the coverage, so a run that broke
		// halfway (API down, Surefire fork dead) is visible in the report itself
		String testsRun = args.length > 8 ? args[8] : "";
		writeTsv(root, args[3]);
		writeHtml(root, args[2], subtitle, testsRun);
		if (!testsRun.isBlank()) System.out.println("TESTS: " + testsRun);
		System.out.printf("%-62s %8s %10s %10s %10s%n", "Element", "Coverage", "Covered", "Missed", "Total");
		print(root, 0, 2);
		// the grand total closes the table, as the user wants to see it when the table is presented
		System.out.printf("%-62s %8s %10d %10d %10d%n", "TOTAL", percent(root), root.covered, root.missed, root.total());
	}

	/**
	 * The workspace's own artifacts in the local repository, by artifactId: every artifactId-version.jar under the
	 * folder (sources, javadoc and tests jars left out). The artifactId is the module's folder name.
	 */
	/**
	 * Analyzes the classes of a jar or folder. In a jar, the dependencies nested in BOOT-INF/lib are skipped: they never
	 * count (only classes whose source is in the module do), and JaCoCo fails on some third-party classes there (on
	 * 2026-10-04 a log4j class inside the jn API jar aborted the whole report).
	 */
	static void analyzeOwnClasses(Analyzer analyzer, File classes) throws IOException {
		if (classes.isDirectory()) {
			analyzer.analyzeAll(classes);
			return;
		}
		try (java.util.zip.ZipFile zip = new java.util.zip.ZipFile(classes)) {
			java.util.Enumeration<? extends java.util.zip.ZipEntry> entries = zip.entries();
			while (entries.hasMoreElements()) {
				java.util.zip.ZipEntry entry = entries.nextElement();
				String name = entry.getName();
				if (!name.endsWith(".class") || name.startsWith("BOOT-INF/lib/")) continue;
				try (java.io.InputStream in = zip.getInputStream(entry)) {
					analyzer.analyzeClass(in, classes + "@" + name);
				} catch (IOException e) {
					System.out.println("WARNING: skipped " + name + ": " + e.getMessage());
				}
			}
		}
	}

	static Map<String, File> findSnapshotJars(File folder) throws IOException {
		Map<String, File> jars = new HashMap<>();
		if (!folder.isDirectory()) return jars;
		try (Stream<Path> paths = Files.walk(folder.toPath())) {
			paths.filter(p -> p.toString().endsWith(".jar")).forEach(p -> {
				File version = p.getParent().toFile();
				File artifact = version.getParentFile();
				String expected = artifact.getName() + "-" + version.getName() + ".jar";
				if (p.getFileName().toString().equals(expected)) jars.put(artifact.getName(), p.toFile());
			});
		}
		return jars;
	}

	static void sum(Node n) {
		if (n.children.isEmpty()) return;
		n.covered = 0; n.missed = 0;
		for (Node c : n.children.values()) { sum(c); n.covered += c.covered; n.missed += c.missed; }
	}

	static String percent(Node n) {
		return n.total() == 0 ? "0,0 %" : String.format(Locale.forLanguageTag("pt-BR"), "%.1f %%", 100.0 * n.covered / n.total());
	}

	static void print(Node n, int level, int maxLevel) {
		System.out.printf("%-62s %8s %10d %10d %10d%n", "  ".repeat(level) + n.name, percent(n), n.covered, n.missed, n.total());
		if (level < maxLevel) for (Node c : new ArrayList<>(n.children.values())) print(c, level + 1, maxLevel);
	}

	static void writeTsv(Node root, String output) throws IOException {
		StringBuilder sb = new StringBuilder("project\tpackage\tfile\tcoverage\tcovered\tmissed\ttotal\n");
		for (Node p : root.children.values()) for (Node s : p.children.values()) for (Node k : s.children.values()) for (Node f : k.children.values())
			sb.append(p.name).append('\t').append(k.name).append('\t').append(f.name).append('\t').append(percent(f)).append('\t')
			  .append(f.covered).append('\t').append(f.missed).append('\t').append(f.total()).append('\n');
		Files.writeString(Path.of(output), sb.toString(), StandardCharsets.UTF_8);
	}

	static void writeHtml(Node root, String output, String subtitle, String testsRun) throws IOException {
		StringBuilder sb = new StringBuilder();
		// no doctype/html/head/body: the Artifact publish wraps the page in its own skeleton, and browsers render it as is when opened locally
		String dark = "--bg:#17181b;--fg:#e8e8ea;--mut:#9a9aa2;--line:#2c2d33;--hov:#202227;--ok:#3fb95a;--bad:#e0574b;--track:#4a2825;color-scheme:dark";
		sb.append("<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>jobsnow Coverage</title><style>")
		  .append(":root{--bg:#fff;--fg:#1d1d1f;--mut:#6b6b70;--line:#e3e3e8;--hov:#f3f4f8;--ok:#2e9e44;--bad:#c9372c;--track:#f1d4d1}")
		  .append("@media (prefers-color-scheme:dark){:root:not([data-theme=\"light\"]){").append(dark).append("}}")
		  .append(":root[data-theme=\"dark\"]{").append(dark).append("}")
		  .append("body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1100px;margin:0 auto;padding-block:20px;padding-inline:16px}")
		  .append("h1{font-size:18px;margin:0 0 4px}p{color:var(--mut);margin:0 0 16px}p.tests{color:var(--fg);margin:4px 0 6px}.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:640px}")
		  .append("th,td{padding:3px 8px;border-bottom:1px solid var(--line);white-space:nowrap}th{text-align:left;font-weight:600;position:sticky;top:env(safe-area-inset-top,0px);background:var(--bg)}")
		  .append("td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}tr:hover td{background:var(--hov)}tr.h{display:none}.t{cursor:pointer;user-select:none}")
		  .append(".t::before{content:'\\25B8';display:inline-block;width:14px;color:var(--mut)}.t.o::before{content:'\\25BE'}.bar{display:inline-block;width:60px;height:9px;background:var(--track);vertical-align:middle;margin-right:6px}")
		  .append(".bar i{display:block;height:100%;background:var(--ok)}.lv1{padding-left:22px}.lv2{padding-left:40px}.lv3{padding-left:58px}.lv4{padding-left:76px}.leaf{padding-left:14px}</style><main>")
		  .append("<h1>Coverage Report</h1>")
		  .append(testsRun.isBlank() ? "" : "<p class='tests'><b>Tests run:</b> " + escape(testsRun) + "</p>")
		  .append("<p>").append(escape(subtitle)).append(" Click a row to expand.</p>")
		  .append("<div class='wrap'><table><thead><tr><th>Element</th><th class='n'>Coverage</th><th class='n'>Covered Instructions</th><th class='n'>Missed Instructions</th><th class='n'>Total Instructions</th></tr></thead><tbody>");
		int[] id = {0};
		html(root, 0, -1, sb, id);
		sb.append("</tbody></table></div></main><script>document.querySelectorAll('.t').forEach(function(r){r.addEventListener('click',function(){var o=r.classList.toggle('o');var id=r.dataset.id;")
		  .append("function f(p,show){document.querySelectorAll('tr[data-p=\"'+p+'\"]').forEach(function(c){c.classList.toggle('h',!show);if(!show||!c.classList.contains('o')){if(c.dataset.id)f(c.dataset.id,false)}else{f(c.dataset.id,true)}})}f(id,o)})});</script>");
		Files.writeString(Path.of(output), sb.toString(), StandardCharsets.UTF_8);
	}

	static void html(Node n, int level, int parent, StringBuilder sb, int[] id) {
		int mine = id[0]++;
		boolean leaf = n.children.isEmpty();
		String cls = (level > 1 ? "h " : "") + (leaf ? "" : "t") + (level == 0 ? " o" : "");
		double p = n.total() == 0 ? 0 : 100.0 * n.covered / n.total();
		sb.append("<tr class='").append(cls.trim()).append("' data-id='").append(mine).append("'").append(parent >= 0 ? " data-p='" + parent + "'" : "").append(">")
		  .append("<td class='lv").append(level).append(leaf ? " leaf" : "").append("'>").append(escape(n.name)).append("</td>")
		  .append("<td class='n'><span class='bar'><i style='width:").append(String.format(Locale.ROOT, "%.1f", p)).append("%'></i></span>").append(percent(n)).append("</td>")
		  .append("<td class='n'>").append(n.covered).append("</td><td class='n'>").append(n.missed).append("</td><td class='n'>").append(n.total()).append("</td></tr>");
		for (Node c : n.children.values()) html(c, level + 1, mine, sb, id);
	}

	static String escape(String s) { return s.replace("&", "&amp;").replace("<", "&lt;"); }
}
