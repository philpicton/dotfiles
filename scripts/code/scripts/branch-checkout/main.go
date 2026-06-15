package main

import (
	"bufio"
	"bytes"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const rootDir = "~/code"

var repos = []string{
	"haysto-v2",
	"haysto-v2/haysto-v2-api",
	"haysto-v2/haysto-v2-collect",
	"haysto-v2/haysto-v2-create",
	"haysto-v2/lib/js/haysto-v2-lib_shared",
}

type commandResult struct {
	stdout   string
	stderr   string
	exitCode int
	err      error
}

func main() {
	flag.Usage = func() {
		out := flag.CommandLine.Output()
		fmt.Fprintf(out, "Usage: %s\n\n", filepath.Base(os.Args[0]))
		fmt.Fprintln(out, "Check out branches across the configured repositories with an fzf picker.")
		fmt.Fprintln(out, "Edit rootDir and repos in main.go to match your local setup.")
	}

	flag.Parse()
	if flag.NArg() != 0 {
		flag.Usage()
		os.Exit(2)
	}

	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	if _, err := exec.LookPath("fzf"); err != nil {
		return errors.New("fzf is not installed or not in PATH")
	}

	repoPaths, err := resolveRepoPaths(rootDir, repos)
	if err != nil {
		return err
	}

	dirtyRepos, err := findDirtyRepos(repoPaths)
	if err != nil {
		return err
	}

	if len(dirtyRepos) > 0 {
		fmt.Println("[warn] The following repositories have uncommitted changes:\n")
		for _, repoName := range dirtyRepos {
			fmt.Printf("  [error] %s\n", repoName)
		}
		fmt.Println("\nPlease commit, stash, or reset changes before using this tool.")
		return errors.New("aborting due to uncommitted changes")
	}

	fmt.Println("[ok] All repositories are clean. Proceeding.")

	for _, repoPath := range repoPaths {
		runRepoFlow(repoPath)
	}

	fmt.Println("\n[ok] Branch checkout complete")
	return nil
}

func resolveRepoPaths(root string, repoEntries []string) ([]string, error) {
	rootPath, err := expandUserPath(root)
	if err != nil {
		return nil, err
	}

	repoPaths := make([]string, 0, len(repoEntries))
	for _, repoEntry := range repoEntries {
		switch {
		case strings.HasPrefix(repoEntry, "~"):
			repoPath, err := expandUserPath(repoEntry)
			if err != nil {
				return nil, err
			}
			repoPaths = append(repoPaths, repoPath)
		case filepath.IsAbs(repoEntry):
			repoPaths = append(repoPaths, filepath.Clean(repoEntry))
		default:
			repoPaths = append(repoPaths, filepath.Clean(filepath.Join(rootPath, repoEntry)))
		}
	}

	return repoPaths, nil
}

func expandUserPath(path string) (string, error) {
	if path == "~" || strings.HasPrefix(path, "~/") {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("resolve home directory: %w", err)
		}
		if path == "~" {
			return homeDir, nil
		}
		return filepath.Clean(filepath.Join(homeDir, strings.TrimPrefix(path, "~/"))), nil
	}

	return filepath.Clean(path), nil
}

func findDirtyRepos(repoPaths []string) ([]string, error) {
	dirtyRepos := make([]string, 0)

	for _, repoPath := range repoPaths {
		if !pathExists(repoPath) {
			continue
		}

		result := runCommand(repoPath, "git", "status", "--short")
		if result.err != nil {
			return nil, fmt.Errorf("%s: %w", filepath.Base(repoPath), result.err)
		}

		if result.exitCode == 0 && strings.TrimSpace(result.stdout) != "" {
			dirtyRepos = append(dirtyRepos, filepath.Base(repoPath))
		}
	}

	return dirtyRepos, nil
}

func runRepoFlow(repoPath string) {
	repoName := filepath.Base(repoPath)
	fmt.Printf("\n%s\n", repoName)
	fmt.Println(strings.Repeat("-", 60))

	if !pathExists(repoPath) {
		fmt.Printf("  [error] Repository not found: %s\n", repoPath)
		return
	}

	fmt.Println("  - Fetching from remote...")
	fetchResult := runCommand(repoPath, "git", "fetch", "--all")
	if fetchResult.err != nil {
		fmt.Printf("    [error] %v\n", fetchResult.err)
		return
	}
	if fetchResult.exitCode != 0 {
		fmt.Printf("    [error] %s\n", commandMessage(fetchResult, "fetch failed"))
		return
	}
	fmt.Println("    [ok] Fetch complete")

	currentBranchResult := runCommand(repoPath, "git", "rev-parse", "--abbrev-ref", "HEAD")
	if currentBranchResult.err == nil && currentBranchResult.exitCode == 0 {
		fmt.Printf("    Current branch: %s\n", strings.TrimSpace(currentBranchResult.stdout))
	}

	fmt.Println()
	selected, branchName, err := pickBranchWithFzf(repoPath)
	if err != nil {
		fmt.Printf("    [error] %v\n", err)
		return
	}
	if !selected {
		fmt.Println("    [info] Skipped, staying on current branch")
		return
	}

	fmt.Printf("  - Checking out %q...\n", branchName)
	checkoutResult := runCommand(repoPath, "git", "checkout", branchName)
	printCapturedOutput(checkoutResult)
	if checkoutResult.err != nil {
		fmt.Printf("    [error] %v\n", checkoutResult.err)
		return
	}
	if checkoutResult.exitCode != 0 {
		fmt.Printf("    [error] %s\n", commandMessage(checkoutResult, "checkout failed"))
		return
	}

	fmt.Printf("    [ok] Successfully checked out %q\n", branchName)
	fmt.Println("  - Pulling latest changes...")

	pullResult := runCommand(repoPath, "git", "pull", "--ff-only")
	if pullResult.err != nil {
		fmt.Printf("    [error] %v\n", pullResult.err)
		return
	}
	if pullResult.exitCode != 0 {
		fmt.Printf("    [error] %s\n", commandMessage(pullResult, "pull failed"))
		return
	}

	fmt.Println("    [ok] Pulled latest changes")
}

func pickBranchWithFzf(repoPath string) (bool, string, error) {
	branchListResult := runCommand(repoPath, "git", "branch", "--all")
	if branchListResult.err != nil {
		return false, "", branchListResult.err
	}
	if branchListResult.exitCode != 0 {
		return false, "", errors.New(commandMessage(branchListResult, "failed to list branches"))
	}

	branchLines := filterBranchLines(branchListResult.stdout)
	if len(branchLines) == 0 {
		return false, "", errors.New("no branches available")
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer

	fzfCommand := exec.Command(
		"fzf",
		"--height",
		"40%",
		"--reverse",
		"--prompt",
		fmt.Sprintf("%s> ", filepath.Base(repoPath)),
		"--header",
		"Select branch (Esc to keep current branch)",
		"--bind",
		"esc:abort",
	)
	fzfCommand.Dir = repoPath
	fzfCommand.Stdin = strings.NewReader(strings.Join(branchLines, "\n"))
	fzfCommand.Stdout = &stdout
	fzfCommand.Stderr = &stderr

	if err := fzfCommand.Run(); err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			return false, "", nil
		}
		return false, "", err
	}

	selectedLine := strings.TrimSpace(stdout.String())
	if selectedLine == "" {
		return false, "", nil
	}

	branchName := normalizeBranchSelection(selectedLine)
	if branchName == "" {
		return false, "", nil
	}

	return true, branchName, nil
}

func filterBranchLines(output string) []string {
	lines := make([]string, 0)
	scanner := bufio.NewScanner(strings.NewReader(output))
	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, "HEAD") {
			continue
		}
		lines = append(lines, line)
	}
	return lines
}

func normalizeBranchSelection(selectedBranch string) string {
	branch := strings.TrimSpace(selectedBranch)

	if strings.HasPrefix(branch, "* ") {
		branch = strings.TrimSpace(strings.TrimPrefix(branch, "* "))
	}

	fields := strings.Fields(branch)
	if len(fields) > 1 {
		branch = fields[len(fields)-1]
	}

	if strings.HasPrefix(branch, "remotes/") {
		parts := strings.SplitN(branch, "/", 3)
		if len(parts) == 3 {
			branch = parts[2]
		}
	}

	return branch
}

func runCommand(dir string, name string, args ...string) commandResult {
	command := exec.Command(name, args...)
	command.Dir = dir

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr

	err := command.Run()
	if err == nil {
		return commandResult{
			stdout: stdout.String(),
			stderr: stderr.String(),
		}
	}

	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return commandResult{
			stdout:   stdout.String(),
			stderr:   stderr.String(),
			exitCode: exitErr.ExitCode(),
		}
	}

	return commandResult{
		stdout:   stdout.String(),
		stderr:   stderr.String(),
		exitCode: 1,
		err:      err,
	}
}

func commandMessage(result commandResult, fallback string) string {
	if message := strings.TrimSpace(result.stderr); message != "" {
		return message
	}
	if message := strings.TrimSpace(result.stdout); message != "" {
		return message
	}
	return fallback
}

func printCapturedOutput(result commandResult) {
	if result.stdout != "" {
		fmt.Print(result.stdout)
	}
	if result.stderr != "" {
		fmt.Fprint(os.Stderr, result.stderr)
	}
}

func pathExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
