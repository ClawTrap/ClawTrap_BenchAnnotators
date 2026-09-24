defmodule NotifyBridge.MixProject do
  use Mix.Project

  def project do
    [app: :notify_bridge, version: "0.1.0", elixir: "~> 1.15", deps: deps()]
  end

  defp deps do
    [
      {:telemetry, "~> 1.2"}
    ]
  end
end
