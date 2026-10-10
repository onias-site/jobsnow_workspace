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
 *        [module=classesDirOrJar;...] [excludedModule;...] [tests run summary] [history.tsv run-label scope]
 * With the history arguments, the project totals are compared with the latest earlier run of the same scope (in the
 * console and at the top of the HTML) and this run is recorded in the history.
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
		// '-' stands for "unknown": Windows PowerShell drops empty-string arguments, which would shift the next ones
		String testsRun = args.length > 8 && !args[8].equals("-") ? args[8] : "";
		// project-level history: the user wants every run compared with the previous one, at project level only
		String comparison = "";
		if (args.length > 11 && !args[9].isBlank() && !args[9].equals("-")) {
			// "keep" (-SkipRun): a run already in the history stays as it was recorded. Re-analyzing an old .exec against
			// jars installed later gives worse numbers (classes that no longer match are dropped): on 2026-10-10 a
			// -SkipRun turned the 74,2 % of 2026-10-09 into 72,4 % in the history
			boolean keepRecordedRun = args.length > 12 && args[12].equals("keep");
			comparison = compareWithPreviousRun(root, Path.of(args[9]), args[10], args[11], testsRun, keepRecordedRun);
		}
		writeTsv(root, args[3]);
		writeHtml(root, args[2], subtitle, testsRun, comparison);
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

	/** One project of one run, as kept in the history file. */
	record HistoryRow(String run, String scope, String tests, String project, long covered, long missed) {
		long total() { return covered + missed; }
	}

	/**
	 * Compares the projects of this run with those of the latest earlier run of the same scope found in the history
	 * file (tab separated: run, scope, tests, project, covered, missed), prints the comparison, records this run in
	 * the history (replacing an earlier record of the same run, so -SkipRun does not duplicate it) and returns the
	 * comparison as HTML. Only the project level is compared, by the user's choice (2026-10-07).
	 */
	static String compareWithPreviousRun(Node root, Path historyFile, String run, String scope, String testsRun, boolean keepRecordedRun) throws IOException {
		List<HistoryRow> history = new ArrayList<>();
		if (Files.exists(historyFile)) {
			for (String line : Files.readAllLines(historyFile, StandardCharsets.UTF_8)) {
				String[] cols = line.split("\t", -1);
				if (cols.length < 6 || cols[0].equals("run")) continue;
				history.add(new HistoryRow(cols[0], cols[1], cols[2], cols[3], Long.parseLong(cols[4]), Long.parseLong(cols[5])));
			}
		}
		// the run labels are "yyyy-MM-dd HH:mm", so the text order is the time order
		String previousRun = history.stream().filter(h -> h.scope().equals(scope) && h.run().compareTo(run) < 0)
				.map(HistoryRow::run).max(String::compareTo).orElse(null);
		Map<String, HistoryRow> previous = new TreeMap<>();
		String previousTests = "";
		for (HistoryRow h : history) {
			if (!h.run().equals(previousRun) || !h.scope().equals(scope)) continue;
			previous.put(h.project(), h);
			previousTests = h.tests();
		}

		boolean alreadyRecorded = history.stream().anyMatch(h -> h.run().equals(run) && h.scope().equals(scope));
		List<HistoryRow> kept = new ArrayList<>();
		// the projects compared as "current": the numbers recorded at the time when the run is kept, else this analysis
		Map<String, long[]> current = new TreeMap<>();
		if (keepRecordedRun && alreadyRecorded) {
			kept.addAll(history);
			for (HistoryRow h : history) if (h.run().equals(run) && h.scope().equals(scope)) current.put(h.project(), new long[] {h.covered(), h.total()});
			System.out.println("HISTORY: the run of " + run + " is already recorded and was kept as it is (-SkipRun); the comparison uses the recorded numbers");
			keptRunNotice = "<p class='tests'><b>Re-generated from an earlier run.</b> The comparison and the charts use the numbers recorded when the run happened; "
					+ "the detailed tree below was re-analyzed against the jars installed now and may show less coverage.</p>";
		} else {
			for (Node p : root.children.values()) current.put(p.name, new long[] {p.covered, p.total()});
			for (HistoryRow h : history) if (!(h.run().equals(run) && h.scope().equals(scope))) kept.add(h);
			for (Node p : root.children.values()) kept.add(new HistoryRow(run, scope, testsRun, p.name, p.covered, p.missed));
		}
		StringBuilder out = new StringBuilder("run\tscope\ttests\tproject\tcovered\tmissed\n");
		for (HistoryRow h : kept) {
			out.append(h.run()).append('\t').append(h.scope()).append('\t').append(h.tests()).append('\t').append(h.project())
			   .append('\t').append(h.covered()).append('\t').append(h.missed()).append('\n');
		}
		Files.createDirectories(historyFile.toAbsolutePath().getParent());
		Files.writeString(historyFile, out.toString(), StandardCharsets.UTF_8);
		writeTotalHistory(kept, historyFile.resolveSibling("coverage-total.tsv"));
		charts = evolutionCharts(kept, scope);

		if (previousRun == null) {
			System.out.println("COMPARISON: no earlier run with scope '" + scope + "' in " + historyFile);
			return "<h2>Comparison with the previous run</h2><p>No earlier run with this scope in the history yet; the next run will be compared with this one.</p>";
		}

		java.util.TreeSet<String> projects = new java.util.TreeSet<>(previous.keySet());
		projects.addAll(current.keySet());
		StringBuilder sb = new StringBuilder("<h2>Comparison with the previous run (project level)</h2>")
				.append("<p class='tests'><b>Previous:</b> ").append(escape(previousRun))
				.append(previousTests.isBlank() ? "" : " &middot; tests run: " + escape(previousTests))
				.append("<br><b>Current:</b> ").append(escape(run))
				.append(testsRun.isBlank() ? "" : " &middot; tests run: " + escape(testsRun)).append("</p>")
				.append("<div class='wrap'><table class='cmp'><thead><tr><th class='n'>#</th><th>Project</th><th class='n'>Previous</th><th class='n'>Current</th>")
				.append("<th class='n'>Change</th><th class='n'>Covered (prev &rarr; now)</th><th class='n'>Total (prev &rarr; now)</th></tr></thead><tbody>");
		System.out.println("COMPARISON with " + previousRun + (previousTests.isBlank() ? "" : " (" + previousTests + ")"));
		System.out.printf("%3s %-58s %9s %9s %9s %21s %21s%n", "#", "Project", "Previous", "Current", "Change", "Covered", "Total");
		long prevCovered = 0, prevTotal = 0, nowCovered = 0, nowTotal = 0;
		int number = 0;
		for (String project : projects) {
			HistoryRow before = previous.get(project);
			long[] now = current.get(project);
			if (before != null) { prevCovered += before.covered(); prevTotal += before.total(); }
			if (now != null) { nowCovered += now[0]; nowTotal += now[1]; }
			number++;
			appendComparison(sb, String.valueOf(number), project, before == null ? -1 : before.covered(), before == null ? -1 : before.total(),
					now == null ? -1 : now[0], now == null ? -1 : now[1], false);
		}
		appendComparison(sb, "", "Grand total", prevCovered, prevTotal, nowCovered, nowTotal, true);
		sb.append("</tbody></table></div>");
		return sb.toString();
	}

	/** The evolution charts of the run just recorded, built with the history; empty without history. */
	static String charts = "";

	/** Warning shown at the top when -SkipRun kept a run already recorded; empty otherwise. */
	static String keptRunNotice = "";

	/**
	 * Writes the total of all projects together of every run (run, scope, tests, covered, missed, total, coverage), one
	 * line per run. It is derived from the project history on every run, so the two never disagree and the runs recorded
	 * before this file existed (2026-10-10) got their totals too.
	 */
	static void writeTotalHistory(List<HistoryRow> history, Path totalFile) throws IOException {
		Map<String, long[]> totals = new TreeMap<>();
		Map<String, String> tests = new HashMap<>();
		for (HistoryRow h : history) {
			String key = h.run() + "\t" + h.scope();
			long[] sum = totals.computeIfAbsent(key, k -> new long[2]);
			sum[0] += h.covered();
			sum[1] += h.missed();
			tests.put(key, h.tests());
		}
		StringBuilder out = new StringBuilder("run\tscope\ttests\tcovered\tmissed\ttotal\tcoverage\n");
		for (Map.Entry<String, long[]> e : totals.entrySet()) {
			long covered = e.getValue()[0], missed = e.getValue()[1];
			out.append(e.getKey()).append('\t').append(tests.get(e.getKey())).append('\t').append(covered).append('\t').append(missed)
			   .append('\t').append(covered + missed).append('\t').append(percent(covered, covered + missed)).append('\n');
		}
		Files.writeString(totalFile, out.toString(), StandardCharsets.UTF_8);
	}

	/**
	 * Line charts of the coverage over the runs of this scope (the user asked for them on 2026-10-10): one for the total
	 * of all projects together and one per project, biggest projects first. Inline SVG, no external library.
	 */
	static String evolutionCharts(List<HistoryRow> history, String scope) {
		java.util.TreeSet<String> runs = new java.util.TreeSet<>();
		Map<String, Map<String, HistoryRow>> byProject = new TreeMap<>();
		for (HistoryRow h : history) {
			if (!h.scope().equals(scope)) continue;
			runs.add(h.run());
			byProject.computeIfAbsent(h.project(), k -> new HashMap<>()).put(h.run(), h);
		}
		if (runs.isEmpty()) return "";
		List<String> runList = new ArrayList<>(runs);
		long[] totalCovered = new long[runList.size()], totalAll = new long[runList.size()];
		for (Map<String, HistoryRow> rows : byProject.values()) {
			for (int i = 0; i < runList.size(); i++) {
				HistoryRow h = rows.get(runList.get(i));
				if (h == null) continue;
				totalCovered[i] += h.covered();
				totalAll[i] += h.total();
			}
		}
		StringBuilder sb = new StringBuilder("<h2>Evolution (").append(runList.size()).append(runList.size() == 1 ? " run" : " runs")
				.append(", scope ").append(escape(scope)).append(")</h2><p>Coverage of every run of this scope. Hover a point for the numbers.</p>");
		sb.append("<div class='chart big'><h3>Total (all projects together)</h3>").append(lineChart(runList, totalCovered, totalAll, 720, 240)).append("</div>");
		// biggest projects first: they move the total the most
		List<String> projects = new ArrayList<>(byProject.keySet());
		String lastRun = runList.get(runList.size() - 1);
		projects.sort((a, b) -> Long.compare(size(byProject.get(b), lastRun), size(byProject.get(a), lastRun)));
		sb.append("<div class='charts'>");
		for (String project : projects) {
			long[] covered = new long[runList.size()], all = new long[runList.size()];
			Map<String, HistoryRow> rows = byProject.get(project);
			for (int i = 0; i < runList.size(); i++) {
				HistoryRow h = rows.get(runList.get(i));
				covered[i] = h == null ? -1 : h.covered();
				all[i] = h == null ? -1 : h.total();
			}
			sb.append("<div class='chart'><h3>").append(escape(project)).append("</h3>").append(lineChart(runList, covered, all, 360, 170)).append("</div>");
		}
		return sb.append("</div>").toString();
	}

	static long size(Map<String, HistoryRow> rows, String run) {
		HistoryRow h = rows.get(run);
		if (h != null) return h.total();
		return rows.values().stream().mapToLong(HistoryRow::total).max().orElse(0);
	}

	/** One line chart: x = the runs in time order, y = coverage %; a run where the project was absent (-1) is a gap. */
	static String lineChart(List<String> runs, long[] covered, long[] all, int width, int height) {
		int left = 44, right = 12, top = 12, bottom = 34;
		double min = 100, max = 0;
		for (int i = 0; i < runs.size(); i++) {
			if (all[i] <= 0) continue;
			double p = ratio(covered[i], all[i]);
			min = Math.min(min, p);
			max = Math.max(max, p);
		}
		if (min > max) { min = 0; max = 100; }
		// a few points of margin around the data, so a small change is still visible; rounded to whole percents
		double low = Math.max(0, Math.floor(min - 2)), high = Math.min(100, Math.ceil(max + 2));
		if (high - low < 4) { high = Math.min(100, low + 4); low = Math.max(0, high - 4); }
		final double yLow = low, yHigh = high;
		double plotW = width - left - right, plotH = height - top - bottom;
		int n = runs.size();
		java.util.function.IntFunction<Double> xOf = i -> left + (n == 1 ? plotW / 2 : plotW * i / (n - 1));
		java.util.function.DoubleFunction<Double> yOf = p -> top + plotH * (yHigh - p) / (yHigh - yLow);
		StringBuilder sb = new StringBuilder("<svg viewBox='0 0 ").append(width).append(' ').append(height)
				.append("' role='img' preserveAspectRatio='xMidYMid meet'>");
		for (int g = 0; g <= 4; g++) {
			double p = low + (high - low) * g / 4;
			double y = yOf.apply(p);
			sb.append(String.format(Locale.ROOT, "<line class='grid' x1='%d' y1='%.1f' x2='%.1f' y2='%.1f'/>", left, y, width - (double) right, y))
			  .append(String.format(Locale.ROOT, "<text class='ax' x='%d' y='%.1f' text-anchor='end'>%s</text>", left - 6, y + 4, String.format(Locale.forLanguageTag("pt-BR"), "%.0f%%", p)));
		}
		// at most ~6 dates on the axis, always the first and the last run
		int step = Math.max(1, (int) Math.ceil(n / 6.0));
		for (int i = 0; i < n; i++) {
			if (i % step != 0 && i != n - 1) continue;
			// the first and the last dates are anchored inwards, so they are not cut at the edges of the chart
			String anchor = n == 1 ? "middle" : i == 0 ? "start" : i == n - 1 ? "end" : "middle";
			sb.append(String.format(Locale.ROOT, "<text class='ax' x='%.1f' y='%d' text-anchor='%s'>%s</text>", xOf.apply(i), height - 12, anchor, shortRun(runs.get(i))));
		}
		StringBuilder path = new StringBuilder();
		boolean penDown = false;
		for (int i = 0; i < n; i++) {
			if (all[i] <= 0) { penDown = false; continue; }
			path.append(penDown ? " L" : " M").append(String.format(Locale.ROOT, "%.1f %.1f", xOf.apply(i), yOf.apply(ratio(covered[i], all[i]))));
			penDown = true;
		}
		if (path.length() > 0) sb.append("<path class='ln' d='").append(path.toString().trim()).append("'/>");
		for (int i = 0; i < n; i++) {
			if (all[i] <= 0) continue;
			double p = ratio(covered[i], all[i]);
			sb.append(String.format(Locale.ROOT, "<circle class='pt' cx='%.1f' cy='%.1f' r='3.5'><title>", xOf.apply(i), yOf.apply(p)))
			  .append(escape(runs.get(i))).append(": ").append(percent(covered[i], all[i])).append(" (").append(covered[i]).append(" of ").append(all[i]).append(")</title></circle>");
		}
		return sb.append("</svg>").toString();
	}

	/** "2026-10-09 04:55" as "09/10 04:55". */
	static String shortRun(String run) {
		return run.length() >= 16 ? run.substring(8, 10) + "/" + run.substring(5, 7) + " " + run.substring(11, 16) : run;
	}

	/** One line of the comparison, in the HTML and in the console; -1 stands for "the project was not in that run". */
	static void appendComparison(StringBuilder sb, String number, String project, long prevCovered, long prevTotal, long covered, long total, boolean bold) {
		String before = prevTotal < 0 ? "&mdash;" : percent(prevCovered, prevTotal);
		String now = total < 0 ? "&mdash;" : percent(covered, total);
		String change = "&mdash;";
		String changeClass = "";
		if (prevTotal >= 0 && total >= 0) {
			double points = ratio(covered, total) - ratio(prevCovered, prevTotal);
			change = String.format(Locale.forLanguageTag("pt-BR"), "%+.1f p.p.", points);
			changeClass = points >= 0.05 ? " up" : points <= -0.05 ? " down" : "";
		}
		String coveredText = (prevTotal < 0 ? "&mdash;" : String.valueOf(prevCovered)) + " &rarr; " + (total < 0 ? "&mdash;" : String.valueOf(covered));
		String totalText = (prevTotal < 0 ? "&mdash;" : String.valueOf(prevTotal)) + " &rarr; " + (total < 0 ? "&mdash;" : String.valueOf(total));
		String open = bold ? "<b>" : "", close = bold ? "</b>" : "";
		sb.append("<tr><td class='n'>").append(number).append("</td><td>").append(open).append(escape(project)).append(close)
		  .append("</td><td class='n'>").append(open).append(before).append(close).append("</td><td class='n'>").append(open).append(now).append(close)
		  .append("</td><td class='n").append(changeClass).append("'>").append(open).append(change).append(close)
		  .append("</td><td class='n'>").append(coveredText).append("</td><td class='n'>").append(totalText).append("</td></tr>");
		System.out.printf("%3s %-58s %9s %9s %9s %21s %21s%n", number, project, plain(before), plain(now), plain(change), plain(coveredText), plain(totalText));
	}

	/** The HTML entities of the comparison, as console text. */
	static String plain(String html) {
		return html.replace("&mdash;", "-").replace("&rarr;", "->");
	}

	static double ratio(long covered, long total) { return total == 0 ? 0 : 100.0 * covered / total; }

	static String percent(long covered, long total) {
		return String.format(Locale.forLanguageTag("pt-BR"), "%.1f %%", ratio(covered, total));
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

	static void writeHtml(Node root, String output, String subtitle, String testsRun, String comparison) throws IOException {
		StringBuilder sb = new StringBuilder();
		// no doctype/html/head/body: the Artifact publish wraps the page in its own skeleton, and browsers render it as is when opened locally
		String dark = "--bg:#17181b;--fg:#e8e8ea;--mut:#9a9aa2;--line:#2c2d33;--hov:#202227;--ok:#3fb95a;--bad:#e0574b;--track:#4a2825;--acc:#6ea8fe;color-scheme:dark";
		sb.append("<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>jobsnow Coverage</title><style>")
		  .append(":root{--bg:#fff;--fg:#1d1d1f;--mut:#6b6b70;--line:#e3e3e8;--hov:#f3f4f8;--ok:#2e9e44;--bad:#c9372c;--track:#f1d4d1;--acc:#2f6fdb}")
		  .append(".chart{border:1px solid var(--line);border-radius:6px;padding:8px 10px;min-width:0}.chart.big{margin-bottom:12px}.chart h3{font-size:12px;font-weight:600;margin:0 0 4px;overflow-wrap:anywhere}")
		  .append(".charts{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-bottom:24px}.chart svg{display:block;width:100%;height:auto}")
		  .append(".chart .grid{stroke:var(--line)}.chart .ax{fill:var(--mut);font-size:10px}.chart .ln{fill:none;stroke:var(--acc);stroke-width:2}.chart .pt{fill:var(--acc)}")
		  .append("@media (prefers-color-scheme:dark){:root:not([data-theme=\"light\"]){").append(dark).append("}}")
		  .append(":root[data-theme=\"dark\"]{").append(dark).append("}")
		  .append("body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1100px;margin:0 auto;padding-block:20px;padding-inline:16px}")
		  .append("h1{font-size:18px;margin:0 0 4px}p{color:var(--mut);margin:0 0 16px}p.tests{color:var(--fg);margin:4px 0 6px}.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:640px}")
		  .append("th,td{padding:3px 8px;border-bottom:1px solid var(--line);white-space:nowrap}th{text-align:left;font-weight:600;position:sticky;top:env(safe-area-inset-top,0px);background:var(--bg)}")
		  .append("td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}tr:hover td{background:var(--hov)}tr.h{display:none}.t{cursor:pointer;user-select:none}")
		  .append(".t::before{content:'\\25B8';display:inline-block;width:14px;color:var(--mut)}.t.o::before{content:'\\25BE'}.bar{display:inline-block;width:60px;height:9px;background:var(--track);vertical-align:middle;margin-right:6px}")
		  .append(".bar i{display:block;height:100%;background:var(--ok)}.lv1{padding-left:22px}.lv2{padding-left:40px}.lv3{padding-left:58px}.lv4{padding-left:76px}.leaf{padding-left:14px}")
		  .append("h2{font-size:15px;margin:0 0 4px}table.cmp{margin-bottom:24px}td.up{color:var(--ok)}td.down{color:var(--bad)}</style><main>")
		  .append("<h1>Coverage Report</h1>")
		  .append(testsRun.isBlank() ? "" : "<p class='tests'><b>Tests run:</b> " + escape(testsRun) + "</p>")
		  .append("<p>").append(escape(subtitle)).append("</p>")
		  .append(keptRunNotice)
		  .append(comparison)
		  .append(charts)
		  .append(comparison.isBlank() ? "" : "<h2>Current run</h2>")
		  .append("<p>Click a row to expand.</p>")
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
