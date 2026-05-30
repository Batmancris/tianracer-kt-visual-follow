. "$PSScriptRoot\..\kt_demo_lib.ps1"

Describe "Get-KtReadySummary" {
    It "parses READY markers and reports ready state" {
        $lines = @(
            "READY_CHECK CORE_TMUX=YES",
            "READY_CHECK CORE_NODE=YES",
            "READY_CHECK ACKERMANN_PUBLISHER=YES",
            "READY_CHECK ACKERMANN_SUBSCRIBER=YES",
            "READY_TO_FOLLOW: YES"
        )

        $summary = Get-KtReadySummary -Lines $lines

        $summary.Ready | Should Be $true
        $summary.Markers["CORE_TMUX"] | Should Be "YES"
        $summary.Markers["ACKERMANN_SUBSCRIBER"] | Should Be "YES"
        $summary.Blockers.Count | Should Be 0
    }

    It "collects blockers when readiness is NO" {
        $lines = @(
            "READY_CHECK CORE_TMUX=NO",
            "READY_CHECK CORE_NODE=NO",
            "READY_BLOCKER: core tmux session missing",
            "READY_BLOCKER: /tianracer_core node missing",
            "READY_TO_FOLLOW: NO"
        )

        $summary = Get-KtReadySummary -Lines $lines

        $summary.Ready | Should Be $false
        $summary.Markers["CORE_TMUX"] | Should Be "NO"
        $summary.Blockers.Count | Should Be 2
        $summary.Blockers[0] | Should Be "core tmux session missing"
    }
}
